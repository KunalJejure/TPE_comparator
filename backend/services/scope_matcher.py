import re
import math
import logging
from typing import List, Dict, Any, Optional
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# ── Stop Words ───────────────────────────────────────────────────
STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "else", "in", "on",
    "at", "to", "for", "with", "by", "from", "up", "about", "into", "over",
    "after", "is", "are", "was", "were", "be", "been", "being", "have", "has",
    "had", "do", "does", "did", "shall", "will", "should", "would", "can",
    "could", "may", "might", "must", "it", "its", "they", "their", "them",
    "this", "that", "these", "those", "of", "as", "which", "not", "no",
    "so", "than", "too", "very", "just", "also", "each", "every", "all",
    "any", "both", "such", "when", "where", "how", "what", "who", "whom",
    "this", "that", "these", "those", "am", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
}

# ── Domain-Specific Synonym Groups ──────────────────────────────
SYNONYM_GROUPS = [
    ("test", "testing", "tests", "tested", "verify", "verification", "verified", "check", "checking", "checks"),
    ("validate", "validation", "validating", "validated", "validations"),
    ("authenticate", "authentication", "auth", "login", "sign-in", "signin", "sso", "sign-on"),
    ("security", "cybersecurity", "infosec", "secure", "secured"),
    ("vulnerability", "vulnerabilities", "vuln", "exploit", "exploits"),
    ("performance", "perf", "benchmark", "benchmarks", "benchmarking", "load-test", "stress-test"),
    ("api", "apis", "endpoint", "endpoints", "interface", "interfaces", "rest", "restful"),
    ("database", "db", "datastore", "data-store", "storage"),
    ("user", "users", "end-user", "end-users", "customer", "customers"),
    ("acceptance", "uat", "user-acceptance"),
    ("functional", "functionality", "feature", "features"),
    ("requirement", "requirements", "req", "reqs", "spec", "specification", "specifications"),
    ("document", "documentation", "doc", "docs", "report", "reports"),
    ("review", "reviews", "reviewed", "reviewing", "audit", "audits", "auditing"),
    ("deploy", "deployment", "deploying", "deployed", "release", "releases", "rollout"),
    ("integrate", "integration", "integrating", "integrated", "integrations"),
    ("automate", "automation", "automated", "automating"),
    ("monitor", "monitoring", "monitored", "monitors", "observability"),
    ("quality", "qa", "qc", "quality-assurance", "quality-control"),
    ("risk", "risks", "risk-assessment", "risk-analysis", "hazard", "hazards"),
    ("compliance", "compliant", "regulatory", "regulation", "regulations"),
    ("install", "installation", "installing", "setup", "set-up", "configure", "configuration"),
    ("maintain", "maintenance", "maintaining", "upkeep"),
    ("backup", "back-up", "recovery", "restore", "disaster-recovery", "dr"),
    ("train", "training", "trained", "education", "onboarding"),
    ("migrate", "migration", "migrating", "migrated"),
    ("encrypt", "encryption", "encrypted", "cipher", "cryptographic"),
    ("access", "access-control", "permissions", "authorization", "authorize", "rbac"),
    ("network", "networking", "connectivity", "connection", "connections"),
    ("server", "servers", "infrastructure", "infra", "hosting"),
    ("protocol", "protocols", "procedure", "procedures", "process", "processes"),
    ("scope", "coverage", "covered", "covers", "encompass", "encompassing"),
    ("deliverable", "deliverables", "output", "outputs", "artifact", "artifacts"),
    ("plan", "planning", "planned", "plans", "strategy", "strategies"),
    ("assess", "assessment", "assessing", "evaluated", "evaluate", "evaluation"),
]

# Build a fast lookup: word -> canonical form
_SYNONYM_MAP: Dict[str, str] = {}
for group in SYNONYM_GROUPS:
    canonical = group[0]
    for word in group:
        _SYNONYM_MAP[word.lower().replace("-", "")] = canonical

def _normalize(text: str) -> str:
    """Lowercase and collapse whitespace for matching."""
    return re.sub(r"\s+", " ", text.lower().strip())

def _simple_stem(word: str) -> str:
    """Lightweight suffix-stripping stemmer."""
    w = word.lower()
    suffixes = [
        "ational", "ization", "iveness", "fulness", "ousness",
        "ements", "nesses", "ations", "encies", "ments",
        "ating", "ities", "ously", "ively", "ently",
        "tion", "sion", "ness", "ment", "ence", "ance", "able", "ible",
        "ized", "ised", "ises", "izes", "ated", "ally",
        "ity", "ing", "ers", "ies", "ous", "ive",
        "ed", "er", "ly", "es",
    ]
    for sfx in suffixes:
        if len(w) > len(sfx) + 2 and w.endswith(sfx):
            return w[:-len(sfx)]
    if w.endswith("s") and len(w) > 3 and not w.endswith("ss"):
        return w[:-1]
    return w

def _canonicalize(word: str) -> str:
    w = word.lower().replace("-", "")
    if w in _SYNONYM_MAP:
        return _SYNONYM_MAP[w]
    stemmed = _simple_stem(w)
    if stemmed in _SYNONYM_MAP:
        return _SYNONYM_MAP[stemmed]
    return stemmed

def _extract_keywords(text: str) -> List[str]:
    words = re.findall(r'[a-zA-Z0-9][\w-]*', text.lower())
    return [w for w in words if w not in STOP_WORDS and len(w) > 1]

def _extract_canonical_keywords(text: str) -> List[str]:
    return [_canonicalize(w) for w in _extract_keywords(text)]

def _get_ngrams(words: List[str], n: int) -> List[str]:
    return [" ".join(words[i:i + n]) for i in range(len(words) - n + 1)]

def build_tfidf_vectors(scope_items: List[str], paragraphs: List[Dict[str, Any]]) -> Dict[str, Any]:
    all_docs: List[List[str]] = []
    scope_keyword_lists: List[List[str]] = []
    para_keyword_lists: List[List[str]] = []
    
    for item in scope_items:
        kws = _extract_canonical_keywords(item)
        scope_keyword_lists.append(kws)
        all_docs.append(kws)
    
    for para in paragraphs:
        kws = _extract_canonical_keywords(para["text"])
        para_keyword_lists.append(kws)
        all_docs.append(kws)
    
    vocab: Dict[str, int] = {}
    doc_freq: Dict[str, int] = {}
    idx = 0
    
    for doc in all_docs:
        unique_words = set(doc)
        for w in unique_words:
            if w not in vocab:
                vocab[w] = idx
                idx += 1
            doc_freq[w] = doc_freq.get(w, 0) + 1
    
    total_docs = len(all_docs)
    
    def _to_tfidf_vector(words: List[str]) -> Dict[int, float]:
        tf: Dict[str, int] = {}
        for w in words:
            tf[w] = tf.get(w, 0) + 1
        vec: Dict[int, float] = {}
        for w, count in tf.items():
            if w in vocab:
                tf_val = count / max(len(words), 1)
                idf_val = math.log((total_docs + 1) / (doc_freq.get(w, 0) + 1)) + 1
                vec[vocab[w]] = tf_val * idf_val
        return vec
    
    def _cosine_sim(v1: Dict[int, float], v2: Dict[int, float]) -> float:
        common_keys = set(v1.keys()) & set(v2.keys())
        if not common_keys: return 0.0
        dot = sum(v1[k] * v2[k] for k in common_keys)
        mag1 = math.sqrt(sum(v ** 2 for v in v1.values()))
        mag2 = math.sqrt(sum(v ** 2 for v in v2.values()))
        if mag1 == 0 or mag2 == 0: return 0.0
        return dot / (mag1 * mag2)
    
    scope_vectors = [_to_tfidf_vector(kws) for kws in scope_keyword_lists]
    para_vectors = [_to_tfidf_vector(kws) for kws in para_keyword_lists]
    
    return {
        "scope_vectors": scope_vectors,
        "para_vectors": para_vectors,
        "cosine_sim": _cosine_sim,
    }

def find_best_match_in_paragraph(scope_item: str, paragraph_text: str) -> Dict[str, Any]:
    norm_scope = _normalize(scope_item)
    norm_para = _normalize(paragraph_text)

    if norm_scope in norm_para:
        start = norm_para.find(norm_scope)
        return {
            "ratio": 1.0,
            "matched_text": paragraph_text[start:start + len(scope_item)],
            "start": start,
            "end": start + len(norm_scope),
            "match_type": "exact",
        }

    scope_words = norm_scope.split()
    para_words = norm_para.split()
    if not scope_words or not para_words:
        return {"ratio": 0.0, "matched_text": "", "start": -1, "end": -1, "match_type": "none"}

    scope_kw_raw = [w for w in scope_words if w not in STOP_WORDS and len(w) > 1]
    if not scope_kw_raw: scope_kw_raw = scope_words
    scope_kw_canonical = [_canonicalize(w) for w in scope_kw_raw]
    scope_kw_canonical_set = set(scope_kw_canonical)
    scope_bigrams = set(_get_ngrams(scope_kw_canonical, 2)) if len(scope_kw_canonical) >= 2 else set()

    best_ratio = 0.0
    best_start_word = 0
    best_end_word = 0
    best_match_type = "keyword"

    min_ws = max(1, len(scope_kw_raw) - 2)
    max_ws = min(len(para_words) + 1, len(scope_words) + 10)

    for ws in range(min_ws, max_ws):
        for i in range(len(para_words) - ws + 1):
            window_words = para_words[i:i + ws]
            window_str = " ".join(window_words)
            seq_ratio = SequenceMatcher(None, norm_scope, window_str).ratio()
            window_kw_raw = [w for w in window_words if w not in STOP_WORDS and len(w) > 1]
            window_kw_canonical = [_canonicalize(w) for w in window_kw_raw]
            window_kw_canonical_set = set(window_kw_canonical)
            kw_ratio = len(scope_kw_canonical_set & window_kw_canonical_set) / len(scope_kw_canonical_set) if scope_kw_canonical_set else 0.0
            bigram_ratio = 0.0
            if scope_bigrams:
                window_bigrams = set(_get_ngrams(window_kw_canonical, 2))
                if window_bigrams:
                    bigram_ratio = len(scope_bigrams & window_bigrams) / len(scope_bigrams)
            stem_matches = 0
            for skw in scope_kw_raw:
                s_stem = _simple_stem(skw)
                for wkw in window_kw_raw:
                    if _simple_stem(wkw) == s_stem or SequenceMatcher(None, skw, wkw).ratio() > 0.85:
                        stem_matches += 1
                        break
            stem_ratio = stem_matches / max(len(scope_kw_raw), 1)
            combined_ratio = (kw_ratio * 0.35 + stem_ratio * 0.20 + bigram_ratio * 0.20 + seq_ratio * 0.25)
            if kw_ratio == 1.0 and len(scope_kw_canonical_set) >= 2: combined_ratio = max(combined_ratio, 0.92)
            if stem_ratio >= 0.9 and bigram_ratio >= 0.5: combined_ratio = max(combined_ratio, 0.90)

            if combined_ratio > best_ratio:
                best_ratio = combined_ratio
                best_start_word, best_end_word = i, i + ws
                best_match_type = "keyword_full" if kw_ratio == 1.0 else ("phrase" if bigram_ratio > 0.5 else "keyword")

    if best_ratio < 0.40:
        return {"ratio": best_ratio, "matched_text": "", "start": -1, "end": -1, "match_type": "none"}

    char_start = sum(len(w) + 1 for w in para_words[:best_start_word])
    matched_text = " ".join(para_words[best_start_word:best_end_word])
    return {"ratio": best_ratio, "matched_text": matched_text, "start": char_start, "end": char_start + len(matched_text), "match_type": best_match_type}

LLM_VALIDATION_PROMPT = """You are a precise scope coverage validator. Determine if scope items are covered in a validation plan.
SCOPE ITEMS: {scope_items_text}
DOC SECTIONS: {doc_sections_text}
Return STRICT JSON format: {{ "results": [ {{ "scope_item": "...", "covered": true/false, "confidence": 0.0-1.0, "match_type": "full|partial|semantic|not_found", "matched_section": "...", "reasoning": "..." }} ] }}"""

def llm_validate_coverage(unmatched_items: List[Dict[str, Any]], borderline_items: List[Dict[str, Any]], paragraphs: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    import os
    import json
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key: return {}
    items_to_check = (unmatched_items + borderline_items)[:25]
    if not items_to_check: return {}
    
    scope_items_text = "\n".join(f"{i+1}. {item['scope_item']}" for i, item in enumerate(items_to_check))
    doc_sections_text = "\n".join(f"{p['style']}: {p['text']}" for p in paragraphs[:100])[:15000]
    
    try:
        from openai import OpenAI
        client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            temperature=0,
            messages=[
                {"role": "system", "content": "You are a precise scope coverage analysis engine. Output only valid JSON."},
                {"role": "user", "content": LLM_VALIDATION_PROMPT.format(scope_items_text=scope_items_text, doc_sections_text=doc_sections_text)}
            ],
            response_format={"type": "json_object"}
        )
        results = json.loads(response.choices[0].message.content).get("results", [])
        return {r["scope_item"]: r for r in results}
    except Exception as e:
        logger.warning("LLM validation failed: %s", e)
        return {}
