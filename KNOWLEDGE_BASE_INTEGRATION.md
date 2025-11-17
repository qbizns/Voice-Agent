# Knowledge Base Integration Guide

Complete guide for adding domain-specific knowledge to the Voice Agent.

## Overview

The Voice Agent supports two types of knowledge integration:

1. **Unstructured Text Files (RAG)** - For natural language content
2. **Structured Python Data** - For precise queries and numeric data

Both can be used together for optimal results.

---

## Method 1: Text Files (Simple - Recommended for Most Use Cases)

### Add a Document

Simply create a `.txt` or `.md` file in `knowledge_base/`:

```bash
# Create new document
cat > knowledge_base/my_topic.md << 'EOF'
# My Topic

This is information about my topic...

## Section 1
Details about section 1...

## Section 2
More information...
EOF
```

### How It Works

1. **Auto-loading**: Files are loaded on server startup
2. **Chunking**: Large documents split into ~500-character chunks
3. **Embedding**: Each chunk converted to vector using multilingual model
4. **Indexing**: Vectors stored in FAISS for fast similarity search
5. **Retrieval**: User questions matched against chunks using semantic search
6. **RAG**: Retrieved chunks passed to LLM as context

### Example: M1A1 Abrams

See `knowledge_base/m1a1_abrams.md` for a complete example:

```markdown
# دبابة القتال الرئيسية إم1 إيه1 أبرامز

## نظرة عامة
دبابة القتال الرئيسية إم1 إيه1 أبرامز...

## الأداء والحركة
### السرعة
- السرعة القصوى على الطرق: 67 كم/ساعة
...
```

### Restart Server to Load

```bash
python main.py
# Logs will show:
# INFO: Loading documents from knowledge_base
# INFO: Loaded 45 chunks from m1a1_abrams.md
```

### Test It

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "ما هي السرعة القصوى لدبابة إم1 إيه1؟",
    "use_knowledge_base": true
  }'
```

Expected response:
```json
{
  "response": "السرعة القصوى لدبابة إم1 إيه1 على الطرق الممهدة تقريباً 67 كم/ساعة...",
  "sources": ["m1a1_abrams.md"],
  "processing_time_ms": 450.2
}
```

---

## Method 2: Structured Python Data (Advanced - For Precise Queries)

### Use Case

When you need:
- ✅ Instant answers to numeric queries (no LLM needed)
- ✅ Guaranteed accuracy for specifications
- ✅ Sub-millisecond response time
- ✅ Programmatic access to data fields

### Implementation

#### Step 1: Define Your Knowledge Class

```python
# In app/services/structured_knowledge.py

class MyEquipmentKnowledge(StructuredKnowledge):
    """Knowledge about my equipment."""

    def __init__(self):
        data = {
            "id": "my_equipment",
            "specifications": {
                "weight_kg": 1500,
                "max_speed_kmh": 120,
                "range_km": 500
            },
            "context_text_ar": """
            معلومات مفصلة عن المعدات...
            """
        }
        super().__init__(data)

    def answer_question(self, question: str) -> Optional[str]:
        """Answer questions using structured data."""
        question_lower = question.lower()

        if "وزن" in question_lower or "weight" in question_lower:
            weight = self.query_numeric("specifications.weight_kg")
            return f"الوزن {weight} كجم"

        if "سرعة" in question_lower or "speed" in question_lower:
            speed = self.query_numeric("specifications.max_speed_kmh")
            return f"السرعة القصوى {speed} كم/ساعة"

        return None
```

#### Step 2: Register in Service

```python
# In app/services/structured_knowledge.py - StructuredKnowledgeService.__init__()

def __init__(self):
    self.knowledge_items: Dict[str, StructuredKnowledge] = {}

    # Register your knowledge
    self.register_knowledge(M1A1AbramsKnowledge())
    self.register_knowledge(MyEquipmentKnowledge())  # Add this

    logger.info(f"Registered {len(self.knowledge_items)} knowledge items")
```

#### Step 3: Test

```python
from app.services.structured_knowledge import StructuredKnowledgeService

service = StructuredKnowledgeService()
answer = service.query_all("ما هو الوزن؟")
print(answer)  # "الوزن 1500 كجم"
```

### How It Works

```
User Question
     │
     ▼
┌─────────────────────┐
│ Structured Knowledge│ ──→ Direct match? ──→ Return precise answer (0.5ms)
└─────────────────────┘                              ▼
     │                                          ✓ Fast
     │ No match                                 ✓ Accurate
     ▼                                          ✓ No LLM cost
┌─────────────────────┐
│   RAG Knowledge     │ ──→ Search vectors ──→ LLM with context (500ms)
└─────────────────────┘                              ▼
     │                                          ✓ Flexible
     │                                          ✓ Natural language
     ▼
Return LLM response
```

---

## Hybrid Approach (Best of Both Worlds)

**Use both methods together:**

1. **Structured data** for:
   - Technical specifications
   - Numeric values
   - Lists of options
   - Precise facts

2. **Text files** for:
   - Detailed explanations
   - Procedures
   - Historical context
   - Narrative descriptions

### Example: M1A1 Abrams

**Structured (fast, precise):**
- "ما هي السرعة القصوى?" → "67 كم/ساعة" (0.5ms)
- "كم عدد الطاقم?" → "4 أفراد" (0.5ms)

**RAG (flexible, detailed):**
- "كيف يعمل نظام السيطرة على النيران?" → (LLM generates detailed answer from text, 500ms)
- "ما الفرق بين M1A1 و M1A2?" → (LLM compares using context)

---

## Complete Example: Adding Military Equipment Knowledge

### 1. Create Text File

```bash
cat > knowledge_base/my_tank.md << 'EOF'
# دبابة XYZ

## المواصفات العامة
- الوزن: 50 طن
- الطول: 7.5 متر
- العرض: 3.2 متر

## التسليح
المدفع الرئيسي عيار 120 ملم بمدى فعال يصل إلى 3000 متر...

## منظومة الدفاع
تتضمن الدبابة نظام حماية نشط APS يمكنه اعتراض الصواريخ...
EOF
```

### 2. Create Structured Data (Optional)

```python
# In app/services/structured_knowledge.py

class MyTankKnowledge(StructuredKnowledge):
    def __init__(self):
        data = {
            "id": "my_tank",
            "specifications": {
                "weight_tons": 50,
                "length_m": 7.5,
                "width_m": 3.2,
                "main_gun_caliber_mm": 120,
                "max_range_m": 3000
            },
            "armament": {
                "main_gun": "120mm cannon",
                "ammo_rounds": 40
            },
            "context_text_ar": """
            دبابة XYZ من أحدث الدبابات، تزن 50 طن وتحمل مدفع
            عيار 120 ملم...
            """
        }
        super().__init__(data)

    def answer_question(self, question: str) -> Optional[str]:
        q = question.lower()

        if "وزن" in q:
            weight = self.query_numeric("specifications.weight_tons")
            return f"وزن الدبابة {weight} طن"

        if "عيار" in q or "مدفع" in q:
            caliber = self.query_numeric("specifications.main_gun_caliber_mm")
            return f"المدفع الرئيسي عيار {caliber} ملم"

        return None

# Register it
def __init__(self):  # In StructuredKnowledgeService
    self.register_knowledge(MyTankKnowledge())
```

### 3. Restart Server

```bash
python main.py
# Should see:
# INFO: Loaded 12 chunks from my_tank.md
# INFO: Registered structured knowledge: my_tank
```

### 4. Test Both Methods

```python
import asyncio
from app.services.ai_agent import AIAgent
from app.services.knowledge_base import KnowledgeBase

async def test():
    kb = KnowledgeBase()
    kb.load_documents_from_directory("knowledge_base")

    agent = AIAgent(knowledge_base=kb, use_structured_knowledge=True)

    # Test 1: Structured (fast)
    response, sources, time_ms = await agent.generate_response("كم وزن الدبابة؟")
    print(f"Structured: {response} ({time_ms:.2f}ms)")
    # Output: "وزن الدبابة 50 طن (0.8ms)"

    # Test 2: RAG (detailed)
    response, sources, time_ms = await agent.generate_response(
        "كيف يعمل نظام الحماية النشط؟"
    )
    print(f"RAG: {response[:100]}... ({time_ms:.2f}ms)")
    # Output: "نظام الحماية النشط APS يمكنه اعتراض الصواريخ... (520.5ms)"

asyncio.run(test())
```

---

## Testing Your Knowledge Base

### Run Test Suite

```bash
# Test M1A1 knowledge (example)
python examples/test_m1a1_knowledge.py
```

### Expected Output

```
============================================================
M1A1 Abrams Knowledge Base - Test Suite
============================================================

Testing Structured Knowledge (M1A1 Abrams)
============================================================

1. Direct Field Access:
   Speed (road): 67.0 km/h
   Range: 465.0 km
   Weight: 63.0 tons
   Crew size: 4

2. Question Answering:

   س: ما هي السرعة القصوى للدبابة؟
   ج: السرعة القصوى 67.0 كم/ساعة على الطرق الممهدة و48.0 كم/ساعة على الطرق الوعرة

   س: كم عدد أفراد الطاقم؟
   ج: يتكون طاقم الدبابة من 4 أفراد: القائد، الرامي، المعمر، السائق
...
```

### Manual Testing via API

```bash
# Test structured answer (fast)
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "ما هي السرعة القصوى؟"}'

# Response:
# {
#   "response": "السرعة القصوى 67.0 كم/ساعة...",
#   "sources": ["structured_knowledge"],
#   "processing_time_ms": 0.8
# }

# Test RAG answer (detailed)
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "اشرح نظام الرؤية الليلية"}'

# Response:
# {
#   "response": "منظومة الرؤية الليلية تضم جهاز تصوير حراري...",
#   "sources": ["m1a1_abrams.md"],
#   "processing_time_ms": 520.3
# }
```

---

## Performance Comparison

| Method | Use Case | Response Time | Accuracy | Cost |
|--------|----------|---------------|----------|------|
| **Structured** | Precise specs, numbers | 0.5-2ms | 100% | Free |
| **RAG** | Detailed explanations | 200-1000ms | 90-95% | LLM call |
| **Hybrid** | Best of both | 0.5-1000ms | 95-100% | Minimal |

---

## Best Practices

### For Text Files (RAG)

1. **Structure with headings** - Use markdown headers for better chunking
2. **Include keywords** - Add Arabic and English terms
3. **Short paragraphs** - Keep chunks coherent (~300-500 words)
4. **Add examples** - Include Q&A sections
5. **Update regularly** - Re-load on server restart

### For Structured Data

1. **Keep it DRY** - Don't duplicate text file content
2. **Use for facts** - Specs, numbers, lists
3. **Handle variations** - Match different phrasings of questions
4. **Fallback gracefully** - Return None if can't answer
5. **Include context_text** - For RAG fallback

### Hybrid Strategy

```python
# Priority order:
1. Check structured knowledge → Fast, precise answers
2. If no match, use RAG → Flexible, detailed answers
3. If no context found → LLM general knowledge
```

---

## Troubleshooting

### "No documents loaded"

**Cause**: Empty knowledge_base directory

**Fix**:
```bash
# Verify files exist
ls knowledge_base/

# Check logs
grep "Loading documents" logs/voice_agent_*.log
```

### "Structured knowledge not answering"

**Cause**: Question phrasing doesn't match patterns

**Fix**: Add more question variations in `answer_question()`:

```python
def answer_question(self, question: str) -> Optional[str]:
    q = question.lower()

    # Add multiple phrasings
    if any(word in q for word in ["سرعة", "سريع", "speed", "velocity"]):
        ...
```

### "RAG returns irrelevant context"

**Cause**: Poor chunking or embedding mismatch

**Fix**:
1. Improve document structure (use headings)
2. Adjust chunk size in `.env`:
   ```bash
   CHUNK_SIZE=300  # Smaller chunks
   CHUNK_OVERLAP=50
   ```
3. Add more specific keywords

### "Slow response times"

**Optimization**:
```bash
# 1. Use structured knowledge for common queries
# 2. Reduce TOP_K_RESULTS
TOP_K_RESULTS=2  # Instead of 3

# 3. Use faster LLM
OLLAMA_MODEL=llama2:7b  # Instead of 13b

# 4. Reduce max tokens
MAX_TOKENS=200  # Instead of 500
```

---

## Migration from Python Dict

If you have a Python dictionary like the M1A1 example:

### Step 1: Extract Context Text

```python
context_ar = my_knowledge_dict["context_text_ar"]

# Save to file
with open("knowledge_base/my_data.md", "w") as f:
    f.write(context_ar)
```

### Step 2: Create Structured Class (Optional)

```python
class MyKnowledge(StructuredKnowledge):
    def __init__(self):
        super().__init__(my_knowledge_dict)

    def answer_question(self, question: str) -> Optional[str]:
        # Implement question matching
        ...
```

### Step 3: Register and Test

```python
# In structured_knowledge.py
self.register_knowledge(MyKnowledge())

# Test
python examples/test_m1a1_knowledge.py
```

---

## Examples in This Repo

1. **M1A1 Abrams** (`knowledge_base/m1a1_abrams.md`)
   - Complete military equipment example
   - Arabic text with technical specs
   - Works with both RAG and structured queries

2. **Test Suite** (`examples/test_m1a1_knowledge.py`)
   - Demonstrates all features
   - Shows structured vs RAG comparison
   - Includes integrated testing

3. **Structured Knowledge** (`app/services/structured_knowledge.py`)
   - M1A1AbramsKnowledge class
   - Question answering logic
   - Service registration

---

## Next Steps

1. **Add your domain knowledge** to `knowledge_base/`
2. **Test with curl** or Python examples
3. **Monitor logs** for loading confirmation
4. **Optimize** based on response times
5. **Extend** with structured data if needed

For questions or issues, see:
- `README.md` - General setup
- `SETUP.md` - Installation guide
- `examples/` - Usage examples
