"""Test script for M1A1 Abrams knowledge base integration."""

import asyncio
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.structured_knowledge import M1A1AbramsKnowledge, StructuredKnowledgeService
from app.services.knowledge_base import KnowledgeBase
from app.core.config import get_settings


def test_structured_knowledge():
    """Test structured knowledge queries."""
    print("=" * 60)
    print("Testing Structured Knowledge (M1A1 Abrams)")
    print("=" * 60)

    m1a1 = M1A1AbramsKnowledge()

    # Test direct field access
    print("\n1. Direct Field Access:")
    print(f"   Speed (road): {m1a1.query_numeric('mobility.speed.max_speed_road_kmh')} km/h")
    print(f"   Range: {m1a1.query_numeric('mobility.range.without_nbc_km')} km")
    print(f"   Weight: {m1a1.query_numeric('dimensions.combat_weight_tons')} tons")
    print(f"   Crew size: {m1a1.get('crew.size')}")

    # Test question answering
    print("\n2. Question Answering:")
    questions_ar = [
        "ما هي السرعة القصوى للدبابة؟",
        "كم عدد أفراد الطاقم؟",
        "ما هو عيار المدفع الرئيسي؟",
        "ما هو المدى التشغيلي؟",
        "كم وزن الدبابة؟"
    ]

    for question in questions_ar:
        answer = m1a1.answer_question(question)
        print(f"\n   س: {question}")
        print(f"   ج: {answer if answer else 'لم يتم العثور على إجابة في البيانات المنظمة'}")


def test_structured_knowledge_service():
    """Test structured knowledge service."""
    print("\n" + "=" * 60)
    print("Testing Structured Knowledge Service")
    print("=" * 60)

    service = StructuredKnowledgeService()

    # Get M1A1 knowledge
    m1a1 = service.get_knowledge("m1a1_abrams")
    print(f"\n✓ Found knowledge: {m1a1.get('names.ar')}")

    # Test queries through service
    questions = [
        "ما هي سرعة الدبابة؟",
        "كم عدد الطاقم؟",
        "ما نوع المحرك؟"
    ]

    print("\nQuerying through service:")
    for question in questions:
        answer = service.query_all(question)
        print(f"\n   {question}")
        print(f"   → {answer if answer else 'No answer'}")

    # Get context text for RAG
    print("\n" + "-" * 60)
    print("Context text (first 500 chars):")
    print("-" * 60)
    context = m1a1.get_context_text("ar")
    print(context[:500] + "...\n")


async def test_rag_knowledge_base():
    """Test RAG with knowledge base files."""
    print("\n" + "=" * 60)
    print("Testing RAG Knowledge Base (Text Files)")
    print("=" * 60)

    try:
        kb = KnowledgeBase()

        # Load documents
        kb_path = Path("knowledge_base")
        if kb_path.exists():
            kb.load_documents_from_directory(kb_path)
            print(f"\n✓ Loaded documents from {kb_path}")

        # Search for relevant information
        queries = [
            "إم1 إيه1",
            "السرعة القصوى",
            "التسليح الرئيسي",
            "الطاقم"
        ]

        print("\nSearching knowledge base:")
        for query in queries:
            results = kb.search(query, top_k=2)
            print(f"\n   Query: {query}")
            print(f"   Found {len(results)} results")
            if results:
                content, score, metadata = results[0]
                print(f"   Top result (score: {score:.3f}):")
                print(f"   {content[:200]}...")

    except Exception as e:
        print(f"\nError loading knowledge base: {e}")
        print("Make sure m1a1_abrams.md exists in knowledge_base/")


async def test_integrated_query():
    """Test integrated query using both structured and RAG."""
    print("\n" + "=" * 60)
    print("Testing Integrated Query (Structured + RAG)")
    print("=" * 60)

    # Import AI agent (would normally be initialized in main.py)
    from app.services.ai_agent import AIAgent

    try:
        # Initialize knowledge base
        kb = KnowledgeBase()
        kb_path = Path("knowledge_base")
        if kb_path.exists():
            kb.load_documents_from_directory(kb_path)

        # Initialize AI agent with structured knowledge
        agent = AIAgent(knowledge_base=kb, use_structured_knowledge=True)

        # Test questions
        test_questions = [
            "ما هي السرعة القصوى لدبابة إم1 إيه1؟",  # Should use structured
            "أخبرني عن منظومة الرؤية الليلية",           # Should use RAG
            "كم عدد أفراد الطاقم؟",                     # Should use structured
        ]

        print("\nTesting questions:")
        for question in test_questions:
            print(f"\n   س: {question}")
            response, sources, time_ms = await agent.generate_response(question)
            print(f"   ج: {response}")
            print(f"   مصادر: {sources}")
            print(f"   وقت المعالجة: {time_ms:.2f}ms")

    except Exception as e:
        print(f"\nError in integrated test: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("M1A1 Abrams Knowledge Base - Test Suite")
    print("=" * 60)

    # Test 1: Structured knowledge
    test_structured_knowledge()

    # Test 2: Structured knowledge service
    test_structured_knowledge_service()

    # Test 3: RAG knowledge base
    asyncio.run(test_rag_knowledge_base())

    # Test 4: Integrated query
    print("\n\nNote: Integrated test requires Ollama to be running")
    print("Start Ollama with: ollama serve")
    response = input("\nRun integrated test? (y/n): ")
    if response.lower() == 'y':
        asyncio.run(test_integrated_query())

    print("\n" + "=" * 60)
    print("Tests Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
