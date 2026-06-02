"""Parse downloaded SEC 10-K / 10-Q HTML into clean section-aware text blocks."""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from app.logging_config import get_logger

logger = get_logger(__name__)


class ParsedPage(BaseModel):
    """A single page of clean text extracted from an SEC filing."""

    page_number: int = Field(..., ge=0)
    section: str | None = Field(default=None)
    text: str


class ParsedFiling(BaseModel):
    """Structured representation of a parsed SEC filing."""

    ticker: str
    form_type: Literal["10-K", "10-Q"]
    filing_date: date
    accession_number: str
    source_url: str
    pages: list[ParsedPage] = Field(default_factory=list)


def detect_section(page_text: str) -> str | None:
    """Extract SEC 10-K/10-Q section header from page text.

    Matches patterns like:
    - "Item 1A. Risk Factors"
    - "Item 7. Management's Discussion and Analysis"
    - "Item 1. Business"

    Uses a tolerant pattern that handles iXBRL whitespace issues, with post-processing
    to clean up greedy or truncated captures.

    Returns:
        The section title (e.g., "Risk Factors") or None if no match.
    """
    # Match "Item N." followed by title words
    # Capture until we hit common sentence starters, newline, or end of text
    # Allow letters, spaces, commas, apostrophes, ampersands in section name
    # Stop words include: sentence starters (We/The/Our), company names (Inc/Corp), body text indicators
    pattern = re.compile(
        r"Item\s+(\d+[A-Z]?)\.\s*([A-Z][A-Za-z\s,'&]+?)(?=\s+(?:We\s|The\s|Our\s|This\s|In\s|As\s|It\s|These\s|Revenue\s|Operating\s|For\s|Inc\.|Corp\.|designs\s|manufactures\s)|\n|$)",
        re.IGNORECASE,
    )
    match = pattern.search(page_text)
    if not match:
        return None

    section_name = match.group(2).strip()

    # Post-process to fix greedy or truncated captures
    section_name = _normalize_section_name(section_name, page_text, match.end())

    return section_name


def _normalize_section_name(section_name: str, full_text: str, match_end_pos: int) -> str:
    """Normalize section name: fix greedy captures and extend truncated ones.
    
    Args:
        section_name: The initially captured section name
        full_text: The full page text
        match_end_pos: The position in full_text where the regex match ended
    
    Returns:
        Normalized section name (not too greedy, not too short)
    """
    # Cap at 60 characters (real SEC section names are short)
    if len(section_name) > 60:
        section_name = section_name[:60].strip()

    # Strip trailing words that signal we've drifted into body/TOC text
    # These words indicate we've captured too much
    stop_phrases = [
        " Company ",
        " Index ",
        " Page ",
        " Consolidated ",
        " Background ",
        " Overview ",
        " Statements ",
    ]
    for phrase in stop_phrases:
        if phrase in section_name:
            # Cut off at the stop phrase
            idx = section_name.index(phrase)
            section_name = section_name[:idx].strip()
            break

    # Handle inverse problem: section name too short (likely truncated)
    # Only extend SINGLE-WORD sections that look incomplete
    # Examples: "Changes" -> "Changes In and Disagreements With Accountants"
    #           "Market" -> "Market for Registrant's Common Equity"
    # Do NOT extend multi-word sections like "Risk Factors" (already complete)
    # Do NOT extend if next text is a company suffix like "Inc." or "Corp."
    word_count = len(section_name.split())
    if word_count == 1 and len(section_name) < 20 and match_end_pos < len(full_text):
        # Check if next text starts with company suffixes (don't extend in that case)
        remaining_text = full_text[match_end_pos : match_end_pos + 100]
        if re.match(r"^\s+Inc\.|^\s+Corp\.|^\s+LLC", remaining_text, re.IGNORECASE):
            # Next text is a company suffix, don't extend
            return section_name.strip()
        
        # Look ahead to see if there are more title-case words or prepositions
        # Match continuation patterns: prepositions and title-case words (including apostrophes)
        # Stop at body-text indicators (Company, Apple, etc.) or sentence starters
        # Allow: In, and, With, for, of, to, Title-Case words, apostrophes
        extension_pattern = re.compile(
            r"^\s+((?:[Ii]n|[Aa]nd|[Ww]ith|[Ff]or|[Oo]f|[Tt]o|[Oo]n|[A-Z][a-z']+)(?:\s+(?:[Ii]n|[Aa]nd|[Ww]ith|[Ff]or|[Oo]f|[Tt]o|[Oo]n|[A-Z][a-z']+))*)"
        )
        ext_match = extension_pattern.search(remaining_text)
        if ext_match:
            extension = ext_match.group(1).strip()
            
            # Filter out body-text words that shouldn't be part of section names
            body_text_words = ["Company", "Apple", "Corporation", "Inc"]
            words = extension.split()
            filtered_words = []
            for word in words:
                if word in body_text_words:
                    break  # Stop at body text
                filtered_words.append(word)
            
            if filtered_words:
                extension = " ".join(filtered_words)
                extended_name = f"{section_name} {extension}".strip()
                # Only use extension if it's reasonable (not too long, not too many words)
                if len(extended_name) <= 60 and len(extended_name.split()) <= 8:
                    section_name = extended_name

    return section_name.strip()


def _extract_header_field(sgml_header: str, field_name: str) -> str | None:
    """Extract a field value from the SGML header section."""
    pattern = rf"{field_name}:\s*(.+?)(?:\n|$)"
    match = re.search(pattern, sgml_header, re.IGNORECASE)
    return match.group(1).strip() if match else None


def _extract_primary_document(raw_text: str, form_type: str) -> str:
    """Extract the primary filing document from SEC SGML multi-document container.
    
    SEC full-submission.txt files contain multiple DOCUMENT blocks:
    - The primary 10-K/10-Q (inside <TEXT>...</TEXT>)
    - Exhibits (EX-21.1, etc.)
    - JSON metadata (FilingSummary with thousands of XBRL references)
    
    This function extracts ONLY the primary document matching the form_type,
    preventing XBRL metadata pollution.
    
    Args:
        raw_text: The complete SGML file content
        form_type: The target form type (e.g., "10-K", "10-Q")
    
    Returns:
        The extracted primary document text, or raw_text if extraction fails
    """
    # Pattern to find DOCUMENT blocks with their TYPE and TEXT content
    # Match: <DOCUMENT>\n<TYPE>10-K\n...<TEXT>\n...content...\n</TEXT>\n</DOCUMENT>
    document_pattern = re.compile(
        r"<DOCUMENT>\s*<TYPE>([^\n]+)\s+.*?<TEXT>\s*(.*?)</TEXT>",
        re.IGNORECASE | re.DOTALL
    )
    
    matches = list(document_pattern.finditer(raw_text))
    
    if not matches:
        logger.warning("no_document_blocks_found", raw_size=len(raw_text))
        return raw_text  # Fallback to current behavior
    
    # Find the first DOCUMENT block whose TYPE matches the target form_type
    for match in matches:
        doc_type = match.group(1).strip()
        doc_text = match.group(2)
        
        # Case-insensitive match for form type (handles "10-K", "10-k", etc.)
        if doc_type.upper() == form_type.upper():
            logger.info(
                "extracted_primary_document",
                form_type=form_type,
                raw_size=len(raw_text),
                extracted_size=len(doc_text),
                reduction_pct=round((1 - len(doc_text) / len(raw_text)) * 100, 1) if raw_text else 0,
            )
            return doc_text
    
    # No matching document found, fallback
    logger.warning("no_matching_document_found", form_type=form_type, documents_found=len(matches))
    return raw_text


def _strip_xbrl_tags(html_content: str) -> str:
    """Remove XBRL inline tags (ix:*) and other noise elements, normalize whitespace.
    
    This is more aggressive than simple tag unwrapping to handle real-world iXBRL filings
    where taxonomy URLs and accounting codes leak into text.
    
    Strategy:
    - Decompose (remove entirely): ix:hidden, ix:references (pure metadata)
    - Unwrap (keep text): other ix:* tags that wrap actual content
    """
    soup = BeautifulSoup(html_content, "lxml")

    # Remove ix:hidden and ix:references tags AND their contents (pure XBRL metadata)
    for tag_name in ["ix:hidden", "ix:references"]:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Unwrap other ix:* tags but keep their text content (they wrap numbers/text)
    for tag in soup.find_all(re.compile(r"^ix:", re.IGNORECASE)):
        tag.unwrap()

    # Remove noise elements that don't contain readable filing content
    for noise_tag in ["head", "script", "style", "link", "meta", "svg"]:
        for tag in soup.find_all(noise_tag):
            tag.decompose()

    # Remove elements with display:none (hidden XBRL data)
    for tag in soup.find_all(style=re.compile(r"display:\s*none", re.IGNORECASE)):
        tag.decompose()

    # Extract text
    text = soup.get_text(separator=" ", strip=False)

    # Aggressive whitespace normalization
    # Replace non-breaking spaces and other unicode whitespace with regular spaces
    text = text.replace("\xa0", " ")  # non-breaking space
    text = text.replace("\u00a0", " ")  # another non-breaking space variant
    text = text.replace("\u2009", " ")  # thin space
    text = text.replace("\u200b", " ")  # zero-width space

    # Collapse multiple consecutive whitespace (including newlines) to single spaces
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def _is_junk_page(page_text: str) -> bool:
    r"""Determine if a page is XBRL metadata junk rather than readable filing content.
    
    Filters out pages that are:
    - Too short (< 100 chars) - adjusted for test fixtures
    - Mostly URLs (> 50% of text)
    - Mostly accession-number-like patterns (> 30% of text)
    - XBRL JSON taxonomy dumps (requires ALL THREE: role:/Topic:/URI: markers)
    - JSON-heavy content (> 5% braces)
    - Many XBRL reference IDs (> 5 occurrences of r\d+:)
    
    Note: Most XBRL content is now pre-filtered by _extract_primary_document(),
    so these rules are more conservative than before.
    """
    if len(page_text) < 100:
        return True

    # Count URL characters
    url_matches = list(re.finditer(r"https?://\S+", page_text))
    url_char_count = sum(len(m.group()) for m in url_matches)
    if url_char_count / len(page_text) > 0.5:
        return True

    # Count digit-heavy tokens (taxonomy metadata like "dei-20231231" or "us-gaap-2023")
    digit_heavy_matches = list(re.finditer(r"\b\w*\d+(?:[/-]\d+)+\w*\b", page_text))
    digit_heavy_char_count = sum(len(m.group()) for m in digit_heavy_matches)
    if digit_heavy_char_count / len(page_text) > 0.3:
        return True

    # Detect XBRL JSON taxonomy dumps
    # Require ALL THREE markers (not just 2) since primary doc is now pre-extracted
    xbrl_markers = ['"role":', '"Topic":', '"URI":']
    xbrl_marker_count = sum(1 for marker in xbrl_markers if marker in page_text)
    if xbrl_marker_count >= 3:  # All three markers = XBRL JSON dump
        return True

    # Count XBRL reference IDs like "r999":", "r123":
    xbrl_ref_pattern = re.compile(r'"r\d+":', re.IGNORECASE)
    xbrl_ref_matches = xbrl_ref_pattern.findall(page_text)
    if len(xbrl_ref_matches) > 5:  # More than 5 reference IDs = XBRL dump
        return True

    # Count braces (JSON structure markers) - raised threshold from 2% to 5%
    brace_count = page_text.count("{") + page_text.count("}")
    if brace_count / len(page_text) > 0.05:  # More than 5% braces = JSON dump
        return True

    return False


def parse_filing(file_path: Path) -> ParsedFiling:
    """Parse an SEC filing from a full-submission.txt file.

    Args:
        file_path: Path to the full-submission.txt file.

    Returns:
        ParsedFiling with metadata and pages of clean text.

    Raises:
        ValueError: If required metadata is missing or file structure is invalid.
    """
    log = logger.bind(file_path=str(file_path))

    if not file_path.exists():
        raise ValueError(f"File not found: {file_path}")

    # Extract ticker from directory structure: .../TICKER/FORM_TYPE/ACCESSION/file.txt
    try:
        ticker = file_path.parent.parent.parent.name
    except IndexError as exc:
        raise ValueError(f"Cannot extract ticker from path structure: {file_path}") from exc

    log = log.bind(ticker=ticker)

    # Read file content
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        log.error("failed_to_read_file", error=str(exc))
        raise ValueError(f"Failed to read file: {file_path}") from exc

    # Extract SGML header (between <SEC-HEADER> and </SEC-HEADER>)
    header_match = re.search(
        r"<SEC-HEADER>(.*?)</SEC-HEADER>", content, re.DOTALL | re.IGNORECASE
    )
    if not header_match:
        raise ValueError(f"No <SEC-HEADER> found in {file_path}")

    sgml_header = header_match.group(1)

    # Extract metadata
    accession_number = _extract_header_field(sgml_header, "ACCESSION NUMBER")
    if not accession_number:
        raise ValueError(f"Missing ACCESSION NUMBER in {file_path}")

    form_type_raw = _extract_header_field(sgml_header, "CONFORMED SUBMISSION TYPE")
    if form_type_raw not in ("10-K", "10-Q"):
        raise ValueError(
            f"Unsupported form type '{form_type_raw}' in {file_path} (expected 10-K or 10-Q)"
        )
    form_type: Literal["10-K", "10-Q"] = form_type_raw  # type: ignore[assignment]

    filing_date_str = _extract_header_field(sgml_header, "CONFORMED PERIOD OF REPORT")
    if not filing_date_str:
        raise ValueError(f"Missing CONFORMED PERIOD OF REPORT in {file_path}")

    try:
        filing_date = datetime.strptime(filing_date_str, "%Y%m%d").date()
    except ValueError as exc:
        raise ValueError(
            f"Invalid filing date format '{filing_date_str}' in {file_path}"
        ) from exc

    cik = _extract_header_field(sgml_header, "CENTRAL INDEX KEY")
    if not cik:
        raise ValueError(f"Missing CENTRAL INDEX KEY in {file_path}")

    # Build SEC EDGAR URL
    accession_no_dashes = accession_number.replace("-", "")
    source_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dashes}.txt"

    # Extract document content (after </SEC-HEADER>)
    doc_start = header_match.end()
    doc_content = content[doc_start:]

    # CRITICAL: Extract ONLY the primary document (10-K/10-Q) from multi-document SGML
    # SEC files contain multiple DOCUMENT blocks (main filing + exhibits + JSON metadata)
    # We only want the primary filing, not the XBRL JSON metadata
    doc_content = _extract_primary_document(doc_content, form_type)

    # Split by <PAGE> markers BEFORE stripping XBRL (so we preserve page boundaries)
    page_marker_pattern = r"<PAGE>"
    if re.search(page_marker_pattern, doc_content, re.IGNORECASE):
        raw_pages = re.split(page_marker_pattern, doc_content, flags=re.IGNORECASE)
        raw_pages = [p.strip() for p in raw_pages if p.strip()]
    else:
        # Fallback: treat entire content as one page
        raw_pages = [doc_content]

    # Now process each page: strip XBRL, clean, detect section
    pages: list[ParsedPage] = []
    current_section: str | None = None  # Track section for propagation
    
    for idx, page_html in enumerate(raw_pages):
        # Strip XBRL tags from this page
        clean_text = _strip_xbrl_tags(page_html)
        
        # Skip junk pages (XBRL metadata, not readable content)
        if _is_junk_page(clean_text):
            log.debug("skipping_junk_page", page_index=idx, text_length=len(clean_text))
            continue
        
        # For fallback (no PAGE markers), split by character count
        if len(raw_pages) == 1 and len(clean_text) > 3000:
            # Split long single page into chunks
            page_size = 3000
            for sub_idx, i in enumerate(range(0, len(clean_text), page_size)):
                chunk_text = clean_text[i : i + page_size].strip()
                if chunk_text and not _is_junk_page(chunk_text):
                    section = detect_section(chunk_text)
                    # Section propagation: inherit from previous if not detected
                    if section:
                        current_section = section
                    pages.append(
                        ParsedPage(
                            page_number=sub_idx, section=current_section, text=chunk_text
                        )
                    )
        else:
            # Regular page processing
            section = detect_section(clean_text)
            # Section propagation: inherit from previous page if not detected
            if section:
                current_section = section
            pages.append(ParsedPage(page_number=len(pages), section=current_section, text=clean_text))

    log.info(
        "parsed_filing",
        accession_number=accession_number,
        form_type=form_type,
        filing_date=str(filing_date),
        pages_count=len(pages),
        sections_found=sum(1 for p in pages if p.section),
    )

    return ParsedFiling(
        ticker=ticker,
        form_type=form_type,
        filing_date=filing_date,
        accession_number=accession_number,
        source_url=source_url,
        pages=pages,
    )
