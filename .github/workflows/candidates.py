"""
candidates.py - prepares a SHORT LIST of positive stories for the owner to approve and rank.
Nothing is voiced, built or uploaded. Output: ../../approval/candidates.json and candidates.md
"""
import json
import os
import tempfile

import config
import news
import script_writer
import stock


def main():
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "approval")
    os.makedirs(out_dir, exist_ok=True)
    want = int(os.environ.get("CANDIDATE_COUNT", "7"))
    items = news.collect()
    print(f"[cand] {len(items)} leads")
    config.NUM_STORIES, config.EXTRA_CANDIDATES = want + 2, 3
    data = script_writer.write(items)
    stories = data["stories"]
    passed, failed = script_writer.verify(stories)
    if failed:
        fixed = script_writer.repair(failed)
        again_ok, _ = script_writer.verify(fixed)
        passed += again_ok
    seen, uniq = set(), []
    for s in passed:                       # one entry per lead
        k = (s.get("source") or {}).get("link")
        if k and k not in seen:
            seen.add(k)
            uniq.append(s)

    def imp(s):
        try:
            return float(s.get("impact", 5))
        except Exception:
            return 5.0
    ranked = sorted(uniq, key=imp, reverse=True)
    chosen, animals = [], 0
    for s in ranked:
        if str(s.get("topic", "")).lower() == "animals":
            if animals >= 1:
                continue
            animals += 1
        chosen.append(s)
        if len(chosen) >= want:
            break
    texts = [s["narration"] for s in chosen] + [s.get("headline", "") for s in chosen]
    try:
        tr = script_writer.translate(texts)
    except Exception as e:
        print(f"[cand] translation failed: {e}")
        tr = [""] * len(texts)
    eng, eng_h = tr[: len(chosen)], tr[len(chosen):]

    work = tempfile.mkdtemp(prefix="cand_")
    rows = []
    for i, s in enumerate(chosen):
        q = s.get("visual_queries") or []
        head = eng_h[i] or s.get("headline", "")
        text = eng[i] or s["narration"]
        try:
            v = stock.best_photos(head, text, q, os.path.join(work, f"c{i}_v"), want=2, kind="video")
        except Exception as e:
            print(f"[cand] video check failed: {e}")
            v = []
        try:
            p = stock.best_photos(head, text, q, os.path.join(work, f"c{i}_p"), want=2)
        except Exception as e:
            print(f"[cand] photo check failed: {e}")
            p = []
        media = "video + photos" if v and p else "video" if v else "photos" if p else "none (headline card only)"
        rows.append({
            "n": i + 1,
            "headline_hi": s.get("headline", ""),
            "headline_en": head,
            "summary_en": text,
            "topic": s.get("topic"),
            "impact": s.get("impact"),
            "media": media,
            "videos": len(v), "photos": len(p),
            "source": s["source"]["source"],
            "link": s["source"].get("link", ""),
            "lead": s["source"],
        })
        print(f"[cand] {i + 1}. {head} | {media}")
    with open(os.path.join(out_dir, "candidates.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    md = ["# Candidate stories\n"]
    for r in rows:
        md.append(f"## {r['n']}. {r['headline_en']}  ({r['topic']}, impact {r['impact']}/10)\n"
                  f"{r['summary_en']}\n\nPictures: **{r['media']}** - Source: {r['source']} - {r['link']}\n")
    with open(os.path.join(out_dir, "candidates.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"[cand] {len(rows)} candidates saved")


if __name__ == "__main__":
    main()
