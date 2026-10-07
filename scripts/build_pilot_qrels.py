"""Build DRAFT evidence labels from the exact already-uploaded book bytes."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from belleq_lab.chunker import chunk_text, content_hash
from belleq_lab.extractors import extract_text

# Seed evidence passages, not an exhaustive judgement of all relevant passages.
CASES = [
 ('f1','frankenstein.txt','mini-2','In which city was Victor Frankenstein born?', 'I am by birth a Genevese'),
 ('f2','frankenstein.txt','mini-2','At which university did Victor Frankenstein become a student?', 'university of Ingolstadt'),
 ('f3','frankenstein.txt','mini-2','In which month did Victor Frankenstein bring the creature to life?', 'dreary night of November'),
 ('h1','hound-of-the-baskervilles.txt','mini-3','At which hospital did James Mortimer work as a house-surgeon?', 'at Charing Cross Hospital'),
 ('h2','hound-of-the-baskervilles.txt','mini-3','Which prize did Dr. James Mortimer win for Comparative Pathology?', 'Jackson prize for Comparative Pathology'),
 ('h3','hound-of-the-baskervilles.txt','mini-3','What kind of footprints did Dr. Mortimer report to Holmes near Sir Charles’s body?', 'footprints of a gigantic hound'),
 ('p1','persuasion.txt','mini-4','In which county is Sir Walter Elliot’s Kellynch Hall?', 'Kellynch Hall, in Somersetshire'),
 ('p2','persuasion.txt','mini-4','Which book did Sir Walter Elliot read for his own amusement?', 'never took up any book but the Baronetage'),
 ('p3','persuasion.txt','mini-4','What is Anne Elliot’s date of birth?', 'Anne, born August 9, 1787'),
]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--books',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    cases, review, corpus = [], [], {}
    for cid, filename, node, question, anchor in CASES:
        raw=(a.books/filename).read_bytes()
        text=extract_text(raw,filename)
        chunks=chunk_text(text)
        corpus[filename]={'sha256':hashlib.sha256(raw).hexdigest(), 'doc_id':content_hash(text),
                          'chunks':len(chunks), 'categorical_node':node}
        matching=[(i,c) for i,c in enumerate(chunks) if anchor in ' '.join(c.split())]
        if not matching: raise ValueError(f'Anchor absent: {cid}; check exact corpus version')
        cases.append(dict(case_id=cid,query=question,reviewed=False,source=filename,
                          relevant_hashes=sorted({content_hash(c) for _,c in matching}),
                          judgement_scope='seed passages; incomplete until reviewed'))
        review.append(dict(case_id=cid,query=question,anchor=anchor,
                           evidence=[dict(chunk_index=i,content_hash=content_hash(c),text=c) for i,c in matching]))
    (a.output/'queries.jsonl').write_text(''.join(json.dumps(c,ensure_ascii=False)+'\n' for c in cases))
    (a.output/'evidence-review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2))
    (a.output/'corpus.json').write_text(json.dumps(corpus,indent=2))
    print('Draft labels only: review evidence and add other relevant chunks before publishing quality metrics.')

if __name__=='__main__': main()
