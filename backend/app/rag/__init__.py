"""The RAG pipeline, one module per stage.

    extraction.py    PDF / DOCX / TXT  ->  raw text + page map
    cleaning.py      raw text          ->  normalised text
    sectioning.py    normalised text   ->  labelled sections (SKILLS, PROJECTS, ...)
    chunking.py      sections          ->  overlapping chunks + metadata
    embeddings.py    chunk text        ->  vectors
    vector_store.py  vectors           ->  searchable index
    ingest.py        orchestrates everything above
    retriever.py     question          ->  most relevant chunks
    prompts.py       chunks + question ->  a grounded prompt
    llm.py           prompt            ->  Claude
    generation.py    answer            ->  text + citations back to the chunks
"""
