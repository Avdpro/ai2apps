"""Conservative, local-only suffix/prefix matching for ordered screenshot OCR.

Raw OCR is never mutated. Number changes are meaningful; full-page duplicates,
short repeated headers and non-adjacent matches deliberately remain untouched.
"""
import re
import unicodedata
from difflib import SequenceMatcher


def _normalized(line):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', line)).casefold()


def trim_overlap(previous, current):
    """Return (derived text, evidence); bounded to 100 nonempty boundary lines."""
    before=[line for line in previous.splitlines() if line.strip()][-100:]
    after=[(n,line) for n,line in enumerate(current.splitlines(keepends=True)) if line.strip()][:101]
    # Require meaningful fresh content on both sides: independent identical pages
    # are not evidence of a scrolling overlap.
    for count in range(min(len(before)-1,len(after)-1,100),2,-1):
        left=[_normalized(x) for x in before[-count:]]
        right=[_normalized(x[1]) for x in after[:count]]
        if any(len(x)>2000 for x in left+right):continue
        if len(set(left))<3 or sum(map(len,left))<48:continue
        if any(re.findall(r'\d+(?:[.,]\d+)*',a)!=re.findall(r'\d+(?:[.,]\d+)*',b) for a,b in zip(left,right)):continue
        # Every row must agree; a long matching row cannot conceal a short changed row.
        if any(a!=b and (min(len(a),len(b))<12 or SequenceMatcher(None,a,b,autojunk=False).ratio()<.96) for a,b in zip(left,right)):continue
        cut=sum(len(line) for line in current.splitlines(keepends=True)[:after[count-1][0]+1])
        return current[cut:],{'removed_lines':count,'matched_text':''.join(line for _,line in after[:count]),'method':'ocr-boundary/v1'}
    return current,None
