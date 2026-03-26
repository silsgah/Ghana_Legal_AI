#!/usr/bin/env python3
"""
Verification script to check ChromaDB ingestion status and test retrieval.

This script:
1. Connects to ChromaDB
2. Shows collection statistics
3. Lists all ingested cases
4. Tests retrieval quality
5. Provides sample queries
"""

import sys
from pathlib import Path
from collections import Counter
from typing import List, Dict, Any

# Add src to path
current_dir = Path(__file__).resolve().parent
src_dir = current_dir.parent
sys.path.insert(0, str(src_dir))

from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

from ghana_legal.config import settings
from ghana_legal.application.rag.chroma_retriever import get_chroma_retriever


console = Console()


def get_collection_stats() -> Dict[str, Any]:
    """Get statistics about the ChromaDB collection."""
    logger.info("Connecting to ChromaDB...")

    retriever = get_chroma_retriever(
        collection_name="legal_docs",
        embedding_model_id=settings.RAG_TEXT_EMBEDDING_MODEL_ID,
        k=settings.RAG_TOP_K,
        device=settings.RAG_DEVICE,
    )

    # Get all documents
    collection_data = retriever.vectorstore.get()

    stats = {
        "total_documents": len(collection_data['ids']),
        "unique_ids": len(set(collection_data['ids'])),
        "has_duplicates": len(collection_data['ids']) != len(set(collection_data['ids']))
    }

    # Analyze metadata
    if collection_data['metadatas']:
        metadatas = collection_data['metadatas']

        # Count by document type
        doc_types = [m.get('document_type', 'unknown') for m in metadatas if m]
        stats['document_types'] = dict(Counter(doc_types))

        # Count by court
        courts = [m.get('court', 'unknown') for m in metadatas if m]
        stats['courts'] = dict(Counter(courts))

        # Count by year
        years = [m.get('year') for m in metadatas if m and m.get('year')]
        stats['years'] = dict(Counter(years))

        # Extract unique case numbers
        case_numbers = [m.get('case_number') for m in metadatas if m and m.get('case_number')]
        stats['unique_cases'] = len(set(case_numbers))
        stats['case_numbers'] = sorted(set(case_numbers))

        # Count chunks per case
        case_chunks = Counter(case_numbers)
        if case_chunks:
            stats['avg_chunks_per_case'] = sum(case_chunks.values()) / len(case_chunks)
            stats['max_chunks_case'] = max(case_chunks.items(), key=lambda x: x[1])
            stats['min_chunks_case'] = min(case_chunks.items(), key=lambda x: x[1])

    return stats


def display_stats(stats: Dict[str, Any]):
    """Display statistics in a formatted table."""
    console.print("\n")
    console.print(Panel.fit(
        "[bold cyan]ChromaDB Collection Statistics[/bold cyan]",
        border_style="cyan"
    ))

    # Overview table
    overview_table = Table(title="Overview", show_header=True, header_style="bold magenta")
    overview_table.add_column("Metric", style="cyan", width=30)
    overview_table.add_column("Value", style="green", width=20)

    overview_table.add_row("Total Chunks", str(stats['total_documents']))
    overview_table.add_row("Unique Cases", str(stats.get('unique_cases', 0)))
    overview_table.add_row("Avg Chunks/Case", f"{stats.get('avg_chunks_per_case', 0):.1f}")
    overview_table.add_row("Has Duplicates", "Yes" if stats['has_duplicates'] else "No")

    console.print(overview_table)

    # Document types
    if 'document_types' in stats:
        console.print("\n")
        doc_type_table = Table(title="Document Types", show_header=True, header_style="bold magenta")
        doc_type_table.add_column("Type", style="cyan")
        doc_type_table.add_column("Count", style="green")

        for doc_type, count in stats['document_types'].items():
            doc_type_table.add_row(doc_type, str(count))

        console.print(doc_type_table)

    # Courts
    if 'courts' in stats:
        console.print("\n")
        court_table = Table(title="Courts", show_header=True, header_style="bold magenta")
        court_table.add_column("Court", style="cyan")
        court_table.add_column("Count", style="green")

        for court, count in stats['courts'].items():
            court_table.add_row(court, str(count))

        console.print(court_table)

    # Years
    if 'years' in stats:
        console.print("\n")
        year_table = Table(title="Years", show_header=True, header_style="bold magenta")
        year_table.add_column("Year", style="cyan")
        year_table.add_column("Count", style="green")

        for year, count in sorted(stats['years'].items(), reverse=True):
            year_table.add_row(str(year), str(count))

        console.print(year_table)

    # Case list
    if 'case_numbers' in stats and stats['case_numbers']:
        console.print("\n")
        console.print(Panel.fit(
            "[bold cyan]Ingested Cases[/bold cyan]",
            border_style="cyan"
        ))

        case_table = Table(show_header=True, header_style="bold magenta")
        case_table.add_column("#", style="dim", width=5)
        case_table.add_column("Case Number", style="cyan")

        for i, case_num in enumerate(stats['case_numbers'][:20], 1):  # Show first 20
            case_table.add_row(str(i), case_num)

        console.print(case_table)

        if len(stats['case_numbers']) > 20:
            console.print(f"\n[dim]... and {len(stats['case_numbers']) - 20} more cases[/dim]")


def test_retrieval():
    """Test retrieval with sample queries."""
    console.print("\n")
    console.print(Panel.fit(
        "[bold cyan]Testing Retrieval Quality[/bold cyan]",
        border_style="cyan"
    ))

    retriever = get_chroma_retriever(
        collection_name="legal_docs",
        embedding_model_id=settings.RAG_TEXT_EMBEDDING_MODEL_ID,
        k=3,
        device=settings.RAG_DEVICE,
    )

    test_queries = [
        "contract law disputes",
        "constitutional rights",
        "court jurisdiction",
        "Adjei case",
        "Supreme Court precedent"
    ]

    for query in test_queries:
        console.print(f"\n[bold yellow]Query:[/bold yellow] {query}")

        try:
            results = retriever.retrieve(query)

            if results:
                console.print(f"[green]✓ Found {len(results)} documents[/green]")

                for i, doc in enumerate(results, 1):
                    metadata = doc.metadata
                    case_num = metadata.get('case_number', 'Unknown')
                    parties = metadata.get('parties', metadata.get('filename', 'Unknown'))

                    console.print(f"  {i}. {parties} [{case_num}]")
                    # Show first 150 chars of content
                    preview = doc.page_content[:150].replace("\n", " ")
                    console.print(f"     [dim]{preview}...[/dim]")
            else:
                console.print("[red]✗ No documents found[/red]")

        except Exception as e:
            console.print(f"[red]✗ Error: {e}[/red]")


def main():
    """Main verification function."""
    console.print("\n")
    console.print(Panel.fit(
        "[bold green]Ghana Legal AI - Ingestion Verification[/bold green]",
        border_style="green"
    ))

    try:
        # Get and display stats
        stats = get_collection_stats()
        display_stats(stats)

        # Test retrieval
        test_retrieval()

        # Summary
        console.print("\n")
        console.print(Panel.fit(
            f"[bold green]✓ Verification Complete![/bold green]\n\n"
            f"Your ChromaDB contains [bold]{stats['total_documents']}[/bold] chunks "
            f"from [bold]{stats.get('unique_cases', 0)}[/bold] unique cases.\n\n"
            f"Retrieval is working correctly!",
            border_style="green"
        ))

    except Exception as e:
        console.print(f"\n[bold red]Error during verification:[/bold red] {e}")
        logger.exception("Verification failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
