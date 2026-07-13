"""
Core DocuBot class responsible for:
- Loading documents from the docs/ folder
- Building a simple retrieval index (Phase 1)
- Retrieving relevant snippets (Phase 1)
- Supporting retrieval only answers
- Supporting RAG answers when paired with Gemini (Phase 2)
"""

import os
import glob
import re

class DocuBot:
    # Minimum fraction of the query's distinct words that must show up in the
    # retrieved sections before we treat that as "meaningful evidence."
    # Below this, a nonzero score is likely just one incidental word overlap
    # (e.g. a common word like "is") rather than an actual answer to the query.
    MIN_QUERY_COVERAGE = 0.5

    # Common words carrying no real topical signal. Excluded from coverage
    # so a query like "is the database nice" can't pass just because "is"
    # and "the" appear in nearly every document.
    STOPWORDS = {
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
        "of", "in", "on", "at", "to", "for", "and", "or", "but", "with",
        "do", "does", "did", "how", "what", "which", "who", "this", "that",
    }

    def __init__(self, docs_folder="docs", llm_client=None):
        """
        docs_folder: directory containing project documentation files
        llm_client: optional Gemini client for LLM based answers
        """
        self.docs_folder = docs_folder
        self.llm_client = llm_client

        # Load documents into memory
        self.documents = self.load_documents()  # List of (filename, text)

        # Split documents into smaller newline-separated sections so
        # retrieval can return a relevant paragraph instead of a whole file
        self.sections = self.build_sections(self.documents)  # List of (filename, section_text)

        # Build a retrieval index (implemented in Phase 1)
        self.index = self.build_index(self.documents)

    # -----------------------------------------------------------
    # Document Loading
    # -----------------------------------------------------------

    def load_documents(self):
        """
        Loads all .md and .txt files inside docs_folder.
        Returns a list of tuples: (filename, text)
        """
        docs = []
        pattern = os.path.join(self.docs_folder, "*.*")
        for path in glob.glob(pattern):
            if path.endswith(".md") or path.endswith(".txt"):
                with open(path, "r", encoding="utf8") as f:
                    text = f.read()
                filename = os.path.basename(path)
                docs.append((filename, text))
        return docs

    # -----------------------------------------------------------
    # Section Splitting
    # -----------------------------------------------------------

    def _is_heading_only(self, section):
        """True if every line in the section is a markdown heading (starts with '#')."""
        lines = section.splitlines()
        return bool(lines) and all(line.strip().startswith("#") for line in lines)

    def _split_into_sections(self, text):
        """
        Split a document's text into paragraph-sized sections, separated by
        one or more blank lines. Empty sections (extra blank lines) are dropped.

        A section that is only a markdown heading (e.g. "### GET /api/users")
        is glued to the section(s) that follow it, up through the first body
        paragraph. Otherwise a heading and the text describing it end up in
        separate sections, and retrieval can return the description without
        ever mentioning what it's describing.
        """
        raw_sections = re.split(r"\n\s*\n", text)
        raw_sections = [section.strip() for section in raw_sections if section.strip()]

        sections = []
        i = 0
        while i < len(raw_sections):
            section = raw_sections[i]
            i += 1
            while self._is_heading_only(section) and i < len(raw_sections):
                section = section + "\n" + raw_sections[i]
                i += 1
            sections.append(section)

        return sections

    def build_sections(self, documents):
        """
        Flatten each document into its individual sections.
        Returns a list of (filename, section_text) tuples, one per section.
        """
        sections = []
        for filename, text in documents:
            for section in self._split_into_sections(text):
                sections.append((filename, section))
        return sections

    # -----------------------------------------------------------
    # Index Construction (Phase 1)
    # -----------------------------------------------------------

    def _tokenize(self, text):
        """Lowercase word tokens, punctuation stripped."""
        return re.findall(r"[a-z0-9]+", text.lower())

    def build_index(self, documents):
        """
        Build a tiny inverted index mapping lowercase words to the filenames
        of the documents they appear in.

        Example structure:
        {
            "token": ["AUTH.md", "API_REFERENCE.md"],
            "database": ["DATABASE.md"]
        }
        """
        index = {}
        for filename, text in documents:
            for token in set(self._tokenize(text)):
                index.setdefault(token, []).append(filename)
        return index

    # -----------------------------------------------------------
    # Scoring and Retrieval (Phase 1)
    # -----------------------------------------------------------

    def score_document(self, query, text):
        """
        Return a simple relevance score for how well the text matches the query:
        the number of query word occurrences found in the text.
        """
        query_words = self._tokenize(query)
        text_words = self._tokenize(text)
        return sum(text_words.count(word) for word in query_words)

    def retrieve(self, query, top_k=3):
        """
        Score every section against the query and return the top_k
        (filename, section_text) pairs sorted by score descending. Sections
        that score 0 are excluded.
        """
        scored = []
        for filename, section in self.sections:
            score = self.score_document(query, section)
            if score > 0:
                scored.append((score, filename, section))

        scored.sort(key=lambda item: item[0], reverse=True)
        results = [(filename, section) for _, filename, section in scored]
        return results[:top_k]

    # -----------------------------------------------------------
    # Evidence Guardrail
    # -----------------------------------------------------------

    def _content_words(self, text):
        """Tokenize text and drop stopwords, leaving only topical words."""
        return {word for word in self._tokenize(text) if word not in self.STOPWORDS}

    def _has_sufficient_evidence(self, query, snippets):
        """
        Decide whether retrieved snippets are real evidence for the query,
        rather than an incidental keyword overlap.

        Checks, in order:
        1. There are no snippets at all (retrieval found nothing).
        2. The query has no content words to match on (e.g. empty,
           punctuation-only, or made only of stopwords like "is the a"),
           so nothing meaningful could count as evidence.
        3. The snippets collectively cover at least MIN_QUERY_COVERAGE of the
           query's distinct content words. Matching one word out of many is
           not enough to be confident.
        """
        if not snippets:
            return False

        query_words = self._content_words(query)
        if not query_words:
            return False

        combined_text = " ".join(text for _, text in snippets)
        matched_words = query_words & self._content_words(combined_text)
        coverage = len(matched_words) / len(query_words)

        return coverage >= self.MIN_QUERY_COVERAGE

    # -----------------------------------------------------------
    # Answering Modes
    # -----------------------------------------------------------

    def answer_retrieval_only(self, query, top_k=3):
        """
        Phase 1 retrieval only mode.
        Returns raw snippets and filenames with no LLM involved.
        """
        snippets = self.retrieve(query, top_k=top_k)

        if not self._has_sufficient_evidence(query, snippets):
            return "I do not know based on these docs."

        formatted = []
        for filename, text in snippets:
            formatted.append(f"[{filename}]\n{text}\n")

        return "\n---\n".join(formatted)

    def answer_rag(self, query, top_k=3):
        """
        Phase 2 RAG mode.
        Uses student retrieval to select snippets, then asks Gemini
        to generate an answer using only those snippets.
        """
        if self.llm_client is None:
            raise RuntimeError(
                "RAG mode requires an LLM client. Provide a GeminiClient instance."
            )

        snippets = self.retrieve(query, top_k=top_k)

        if not self._has_sufficient_evidence(query, snippets):
            return "I do not know based on these docs."

        return self.llm_client.answer_from_snippets(query, snippets)

    # -----------------------------------------------------------
    # Bonus Helper: concatenated docs for naive generation mode
    # -----------------------------------------------------------

    def full_corpus_text(self):
        """
        Returns all documents concatenated into a single string.
        This is used in Phase 0 for naive 'generation only' baselines.
        """
        return "\n\n".join(text for _, text in self.documents)
