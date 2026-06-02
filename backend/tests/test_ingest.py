"""Tests for the SEC filings ingestion pipeline."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from app.db.models import Chunk as ChunkORM
from app.db.models import Filing
from app.ingest.embedder import OpenAIEmbedder
from app.ingest.html_parser import detect_section, parse_filing
from app.ingest.pipeline import IngestionPipeline

# Synthetic SGML filing fixture
SYNTHETIC_FILING = """<SEC-DOCUMENT>0000123456-25-000001.txt : 20250101
<SEC-HEADER>0000123456-25-000001.hdr.sgml : 20250101
ACCESSION NUMBER:		0000123456-25-000001
CONFORMED SUBMISSION TYPE:	10-K
PUBLIC DOCUMENT COUNT:		1
CONFORMED PERIOD OF REPORT:	20241231
FILED AS OF DATE:		20250102
DATE AS OF CHANGE:		20250102

FILER:
	COMPANY DATA:
		COMPANY CONFORMED NAME:			TEST CORP
		CENTRAL INDEX KEY:			0000123456
		STANDARD INDUSTRIAL CLASSIFICATION:	RETAIL-EATING PLACES [5812]
		IRS NUMBER:				123456789
		STATE OF INCORPORATION:			DE
		FISCAL YEAR END:			1231

	FILING VALUES:
		FORM TYPE:		10-K
		SEC ACT:		1934 Act
		SEC FILE NUMBER:	001-12345
		FILM NUMBER:		25123456

	BUSINESS ADDRESS:
		STREET 1:		123 MAIN ST
		CITY:			NEW YORK
		STATE:			NY
		ZIP:			10001
		BUSINESS PHONE:		2125551234

	MAIL ADDRESS:
		STREET 1:		123 MAIN ST
		CITY:			NEW YORK
		STATE:			NY
		ZIP:			10001
</SEC-HEADER>
<DOCUMENT>
<TYPE>10-K
<SEQUENCE>1
<FILENAME>testcorp-20241231.htm
<DESCRIPTION>FORM 10-K
<TEXT>
<PAGE>
<html>
<body>
<p>Item 1A. Risk Factors</p>
<p>We face supply chain risks including reliance on Asia Pacific manufacturing
centers which could be disrupted by geopolitical events or natural disasters.</p>
<ix:hidden>
    <ix:nonFraction contextRef="c1" name="us-gaap:Assets" unitRef="usd">1234567</ix:nonFraction>
</ix:hidden>
</body>
</html>
</PAGE>
<PAGE>
<html>
<body>
<p>Item 7. Management's Discussion and Analysis</p>
<p>Revenue grew 12% year over year driven by strong demand in our core markets.
Operating margins expanded to 18% from 16% in the prior year.</p>
</body>
</html>
</PAGE>
</TEXT>
</DOCUMENT>
</SEC-DOCUMENT>"""


@pytest.fixture
def synthetic_filing_path(tmp_path: Path) -> Path:
    """Create a synthetic SEC filing file for testing."""
    # Structure: TICKER/FORM/ACCESSION/full-submission.txt
    ticker_dir = tmp_path / "TEST"
    form_dir = ticker_dir / "10-K"
    accession_dir = form_dir / "0000123456-25-000001"
    accession_dir.mkdir(parents=True)

    filing_path = accession_dir / "full-submission.txt"
    filing_path.write_text(SYNTHETIC_FILING)

    return filing_path


@pytest.mark.asyncio
async def test_parse_filing_extracts_metadata(synthetic_filing_path: Path) -> None:
    """Test that parse_filing correctly extracts ticker, form_type, filing_date, accession."""
    parsed = parse_filing(synthetic_filing_path)

    assert parsed.ticker == "TEST"
    assert parsed.form_type == "10-K"
    assert parsed.filing_date == date(2024, 12, 31)
    assert parsed.accession_number == "0000123456-25-000001"
    assert "edgar/data/0000123456" in parsed.source_url


@pytest.mark.asyncio
async def test_parse_filing_yields_pages_with_sections(synthetic_filing_path: Path) -> None:
    """Test that parse_filing splits into pages and detects section headers."""
    parsed = parse_filing(synthetic_filing_path)

    # Should have multiple pages (may include document metadata page before first <PAGE>)
    assert len(parsed.pages) >= 2

    # Find pages with Risk Factors and MD&A sections
    risk_factors_page = next((p for p in parsed.pages if p.section == "Risk Factors"), None)
    mda_page = next((p for p in parsed.pages if p.section == "Management's Discussion and Analysis"), None)

    assert risk_factors_page is not None, "Should find Risk Factors section"
    assert "supply chain risks" in risk_factors_page.text

    assert mda_page is not None, "Should find MD&A section"
    assert "Revenue grew 12%" in mda_page.text


@pytest.mark.parametrize(
    "page_text,expected_section",
    [
        ("Item 1A. Risk Factors\nSome content", "Risk Factors"),
        ("Item 7. Management's Discussion and Analysis\nMD&A content", "Management's Discussion and Analysis"),
        ("Item 1. Business\nCompany overview", "Business"),
        ("Item 1B. Unresolved Staff Comments\nNone", "Unresolved Staff Comments"),
        ("No section header here", None),
        ("item lowercase won't match", None),
        # New: test whitespace normalization (non-breaking spaces from iXBRL)
        ("Item\xa01A.\xa0Risk Factors\nSome content", "Risk Factors"),
        ("Item\u00a01A.\u00a0Risk Factors We face", "Risk Factors"),
    ],
)
def test_detect_section_recognizes_item_headers(page_text: str, expected_section: str | None) -> None:
    """Test section header detection with various formats, including iXBRL whitespace."""
    assert detect_section(page_text) == expected_section


@pytest.mark.asyncio
async def test_parse_filing_strips_xbrl_tags(synthetic_filing_path: Path) -> None:
    """Test that XBRL inline tags are removed but text is preserved."""
    parsed = parse_filing(synthetic_filing_path)

    # The XBRL <ix:hidden> block should be removed
    # BeautifulSoup's get_text() should have extracted text from ix:* tags
    page_text = parsed.pages[0].text
    assert "ix:hidden" not in page_text.lower()
    assert "ix:nonfraction" not in page_text.lower()


@pytest.mark.asyncio
async def test_parse_filing_normalizes_whitespace(tmp_path: Path) -> None:
    """Test that non-breaking spaces and whitespace are normalized for section detection."""
    # Create a filing with non-breaking spaces (common in iXBRL)
    filing_with_nbsp = SYNTHETIC_FILING.replace(
        "Item 1A. Risk Factors",
        "Item\xa01A.\xa0Risk Factors"  # Use non-breaking spaces
    )
    
    # Structure: TICKER/FORM/ACCESSION/full-submission.txt
    ticker_dir = tmp_path / "TEST"
    form_dir = ticker_dir / "10-K"
    accession_dir = form_dir / "0000123456-25-000001"
    accession_dir.mkdir(parents=True)

    filing_path = accession_dir / "full-submission.txt"
    filing_path.write_text(filing_with_nbsp)

    parsed = parse_filing(filing_path)

    # Should still detect "Risk Factors" section despite non-breaking spaces
    risk_factors_page = next((p for p in parsed.pages if p.section == "Risk Factors"), None)
    assert risk_factors_page is not None, "Should detect Risk Factors section even with non-breaking spaces"
    
    # Verify the text has normalized whitespace (no \xa0)
    assert "\xa0" not in risk_factors_page.text


@pytest.mark.asyncio
async def test_junk_filter_rejects_xbrl_json() -> None:
    """Test that pages containing XBRL JSON taxonomy dumps are filtered out."""
    from app.ingest.html_parser import _is_junk_page
    
    # Real XBRL JSON pattern from Apple 10-K
    xbrl_json_page = """
    g/1943274/2147480046/944-40-55-9E" }, "r999": { "role": "http://www.xbrl.org/2003/role/...",
    "Topic": "944", "SubTopic": "605", "URI": "https://asc.fasb.org/1943274/2147480046/944-40-55-9E",
    "r1000": { "role": "http://www.xbrl.org/...", "Topic": "946", "SubTopic": "210" },
    "r1001": { "role": "http://www.xbrl.org/...", "Topic": "850", "SubTopic": "10" },
    "r1002": { "role": "http://www.xbrl.org/...", "Topic": "740", "SubTopic": "10" },
    "r1003": { "role": "http://www.xbrl.org/...", "Topic": "718", "SubTopic": "10" }
    """
    
    assert _is_junk_page(xbrl_json_page), "XBRL JSON with role:/Topic:/URI: should be filtered"
    
    # Test with r\d+: pattern (many XBRL reference IDs)
    xbrl_refs_page = '"r1": {}, "r2": {}, "r3": {}, "r4": {}, "r5": {}, "r6": {}, "r7": {}'
    assert _is_junk_page(xbrl_refs_page), "Many r\\d+: patterns should be filtered"
    
    # Test with high brace density (JSON structure)
    json_heavy_page = "{ } { } { } { } { } { } " * 20  # 2.4% braces
    assert _is_junk_page(json_heavy_page), "High brace density should be filtered"
    
    # Verify normal filing text is NOT filtered
    normal_text = """
    Item 1A. Risk Factors
    We face supply chain risks including reliance on manufacturing centers which could
    be disrupted by geopolitical events. Our revenue depends on consumer demand.
    """
    assert not _is_junk_page(normal_text), "Normal filing text should NOT be filtered"


@pytest.mark.asyncio
async def test_section_name_truncated_when_greedy() -> None:
    """Test that greedy section name captures are normalized to just the section title."""
    from app.ingest.html_parser import detect_section
    
    # Real examples from Apple 10-K where regex captured too much
    greedy_captures = [
        # "Business Company Background" should become "Business"
        ("Item 1. Business Company Background Apple Inc. designs", "Business"),
        # "Financial Statements..." should become "Financial Statements and Supplementary Data"
        ("Item 8. Financial Statements and Supplementary Data Index to Consolidated Financial Statements", 
         "Financial Statements and Supplementary Data"),
        # Section name already clean (should stay the same)
        ("Item 1A. Risk Factors\nWe face risks", "Risk Factors"),
        ("Item 7. Management's Discussion and Analysis\nRevenue grew", "Management's Discussion and Analysis"),
    ]
    
    for text, expected in greedy_captures:
        result = detect_section(text)
        assert result == expected, f"Expected {repr(expected)}, got {repr(result)} for {repr(text[:50])}"


@pytest.mark.asyncio
async def test_extract_primary_document_filters_metadata() -> None:
    """Test that _extract_primary_document extracts only the primary filing, not JSON metadata."""
    from app.ingest.html_parser import _extract_primary_document
    
    # Synthetic multi-document SGML container
    multi_doc_sgml = """<DOCUMENT>
<TYPE>10-K
<SEQUENCE>1
<FILENAME>test-10k.htm
<TEXT>
<html>
<body>
<p>Item 1A. Risk Factors</p>
<p>We face supply chain risks.</p>
</body>
</html>
</TEXT>
</DOCUMENT>
<DOCUMENT>
<TYPE>JSON
<SEQUENCE>2
<FILENAME>FilingSummary.json
<TEXT>
{"role": "http://www.xbrl.org/", "Topic": "944", "URI": "https://asc.fasb.org/"}
</TEXT>
</DOCUMENT>
<DOCUMENT>
<TYPE>EX-21.1
<SEQUENCE>3
<TEXT>
Subsidiaries list...
</TEXT>
</DOCUMENT>"""
    
    result = _extract_primary_document(multi_doc_sgml, "10-K")
    
    # Should contain only 10-K content
    assert "Risk Factors" in result
    assert "supply chain" in result
    
    # Should NOT contain JSON metadata
    assert '"role":' not in result
    assert '"Topic":' not in result
    assert '"URI":' not in result
    
    # Should NOT contain exhibit content
    assert "Subsidiaries list" not in result


@pytest.mark.asyncio
async def test_parse_filing_handles_multi_document_sgml(tmp_path: Path) -> None:
    """Test that parse_filing correctly extracts only 10-K content from multi-document SGML."""
    # Create a realistic multi-document SGML file
    multi_doc_filing = """<SEC-DOCUMENT>0000123456-25-000001.txt : 20250101
<SEC-HEADER>0000123456-25-000001.hdr.sgml : 20250101
ACCESSION NUMBER:		0000123456-25-000001
CONFORMED SUBMISSION TYPE:	10-K
PUBLIC DOCUMENT COUNT:		3
CONFORMED PERIOD OF REPORT:	20241231
FILED AS OF DATE:		20250102
DATE AS OF CHANGE:		20250102

FILER:
	COMPANY DATA:
		COMPANY CONFORMED NAME:			TEST CORP
		CENTRAL INDEX KEY:			0000123456
		STANDARD INDUSTRIAL CLASSIFICATION:	RETAIL [5812]
		IRS NUMBER:				123456789
		STATE OF INCORPORATION:			DE
		FISCAL YEAR END:			1231
</SEC-HEADER>
<DOCUMENT>
<TYPE>10-K
<SEQUENCE>1
<FILENAME>test-10k.htm
<TEXT>
<html>
<body>
<PAGE>
<p>Item 1A. Risk Factors</p>
<p>We face supply chain risks including reliance on manufacturing centers which could be disrupted by geopolitical events or natural disasters. Our business depends on the continued availability of critical components from a limited number of suppliers.</p>
</PAGE>
<PAGE>
<p>Item 7. Management's Discussion and Analysis</p>
<p>Revenue grew 12% year over year driven by strong demand in our core markets. Operating margins expanded to 18% from 16% in the prior year due to improved operational efficiency and favorable product mix.</p>
</PAGE>
</body>
</html>
</TEXT>
</DOCUMENT>
<DOCUMENT>
<TYPE>JSON
<SEQUENCE>2
<FILENAME>FilingSummary.json
<TEXT>
{"role": "http://www.xbrl.org/2003/role/...", "Topic": "944", "URI": "https://asc.fasb.org/...",
 "r999": {"role": "http://www.xbrl.org/", "Topic": "946", "SubTopic": "210"},
 "r1000": {"role": "http://www.xbrl.org/", "Topic": "850", "SubTopic": "10"}}
</TEXT>
</DOCUMENT>
<DOCUMENT>
<TYPE>EX-21.1
<SEQUENCE>3
<FILENAME>ex21-1.htm
<TEXT>
<html><body>List of subsidiaries...</body></html>
</TEXT>
</DOCUMENT>
</SEC-DOCUMENT>"""
    
    # Structure: TICKER/FORM/ACCESSION/full-submission.txt
    ticker_dir = tmp_path / "TEST"
    form_dir = ticker_dir / "10-K"
    accession_dir = form_dir / "0000123456-25-000001"
    accession_dir.mkdir(parents=True)
    
    filing_path = accession_dir / "full-submission.txt"
    filing_path.write_text(multi_doc_filing)
    
    parsed = parse_filing(filing_path)
    
    # Should have extracted pages from 10-K only
    assert len(parsed.pages) >= 2, "Should have at least 2 pages from 10-K"
    
    # Should have readable text with sections
    risk_factors_page = next((p for p in parsed.pages if p.section == "Risk Factors"), None)
    assert risk_factors_page is not None, "Should detect Risk Factors section"
    assert "supply chain" in risk_factors_page.text
    
    mda_page = next((p for p in parsed.pages if p.section == "Management's Discussion and Analysis"), None)
    assert mda_page is not None, "Should detect MD&A section"
    assert "Revenue" in mda_page.text
    
    # Should NOT contain JSON metadata in any page
    for page in parsed.pages:
        assert '"role":' not in page.text, "JSON metadata should not leak into pages"
        assert '"Topic":' not in page.text, "JSON metadata should not leak into pages"
        assert '"r999":' not in page.text, "XBRL reference IDs should not leak into pages"
    
    # Should NOT contain exhibit content
    for page in parsed.pages:
        assert "subsidiaries" not in page.text.lower(), "Exhibit content should not be in pages"


@pytest.fixture
def mock_embedder() -> OpenAIEmbedder:
    """Create a mock embedder that returns deterministic vectors."""
    embedder = MagicMock(spec=OpenAIEmbedder)
    
    async def mock_embed_in_batches(texts: list[str], batch_size: int = 100) -> list[list[float]]:
        # Return deterministic 1536-dim vectors
        return [[0.1] * 1536 for _ in texts]
    
    embedder.embed_in_batches = AsyncMock(side_effect=mock_embed_in_batches)
    return embedder


@pytest.mark.asyncio
async def test_pipeline_idempotency(
    synthetic_filing_path: Path,
    db_session_maker,
    mock_embedder: OpenAIEmbedder,
) -> None:
    """Test that ingesting the same filing twice is idempotent."""
    # Mock the chunker to return some chunks (will be called once per page)
    mock_chunk = MagicMock()
    mock_chunk.text = "Test chunk text"
    mock_chunk.page_number = 0
    mock_chunk.section = "Risk Factors"
    mock_chunk.char_start = 0

    with patch("app.ingest.pipeline.chunker.chunk", return_value=[mock_chunk]):
        pipeline = IngestionPipeline(db_session_maker=db_session_maker, embedder=mock_embedder)

        # First ingestion (will process 2 pages after junk filtering, so 2 chunks total)
        chunks_1 = await pipeline.ingest_filing(synthetic_filing_path)
        assert chunks_1 == 2  # Two pages pass junk filter (first page is only header metadata)

        # Second ingestion (should be idempotent)
        chunks_2 = await pipeline.ingest_filing(synthetic_filing_path)
        assert chunks_2 == 0  # No chunks inserted

    # Verify only one filing in DB
    async with db_session_maker() as session:
        stmt = select(Filing)
        result = await session.execute(stmt)
        filings = result.scalars().all()
        assert len(filings) == 1


@pytest.mark.asyncio
async def test_pipeline_handles_empty_chunker_gracefully(
    synthetic_filing_path: Path,
    db_session_maker,
    mock_embedder: OpenAIEmbedder,
) -> None:
    """Test that pipeline handles chunker returning empty list (stub behavior)."""
    # Use real chunker (which returns empty list as a stub)
    pipeline = IngestionPipeline(db_session_maker=db_session_maker, embedder=mock_embedder)

    chunks_inserted = await pipeline.ingest_filing(synthetic_filing_path)
    assert chunks_inserted == 0

    # Verify Filing was still created
    async with db_session_maker() as session:
        stmt = select(Filing)
        result = await session.execute(stmt)
        filings = result.scalars().all()
        assert len(filings) == 1
        assert filings[0].accession_number == "0000123456-25-000001"

        # Verify no chunks were created
        stmt_chunks = select(ChunkORM)
        result_chunks = await session.execute(stmt_chunks)
        chunks = result_chunks.scalars().all()
        assert len(chunks) == 0

    # Verify embedder was NOT called (no chunks to embed)
    mock_embedder.embed_in_batches.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_inserts_chunks_with_embeddings(
    synthetic_filing_path: Path,
    db_session_maker,
    mock_embedder: OpenAIEmbedder,
) -> None:
    """Test full pipeline: parse → chunk → embed → insert."""
    # Mock chunker to return 3 chunks (will be called once per page, 2 pages total = 6 chunks)
    mock_chunks = [
        MagicMock(text=f"Chunk {i}", page_number=i, section="Risk Factors", char_start=i * 100)
        for i in range(3)
    ]

    with patch("app.ingest.pipeline.chunker.chunk", return_value=mock_chunks):
        pipeline = IngestionPipeline(db_session_maker=db_session_maker, embedder=mock_embedder)
        chunks_inserted = await pipeline.ingest_filing(synthetic_filing_path)

    # 2 pages (after junk filter) * 3 chunks per page = 6 total
    assert chunks_inserted == 6

    # Verify embedder was called with correct texts
    mock_embedder.embed_in_batches.assert_called_once()
    call_args = mock_embedder.embed_in_batches.call_args
    # Should have 6 chunks total (3 per page * 2 pages)
    assert len(call_args[0][0]) == 6
    assert all(text in ["Chunk 0", "Chunk 1", "Chunk 2"] for text in call_args[0][0])

    # Verify chunks in DB
    async with db_session_maker() as session:
        stmt = select(ChunkORM)
        result = await session.execute(stmt)
        chunks = result.scalars().all()
        assert len(chunks) == 6

        # Verify embeddings are stored
        for chunk in chunks:
            assert chunk.embedding is not None
            assert len(chunk.embedding) == 1536
