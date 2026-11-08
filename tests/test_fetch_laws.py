from pathlib import Path

import scripts.fetch_laws as fetch


def test_pdf_failure_does_not_abort(tmp_path, monkeypatch):
    target = {
        "law": "测试法",
        "short_name": "测试法",
        "search_title": "测试法",
        "out_name": "test.json",
        "flxz": "法律",
        "min_article": 1,
        "max_article": 1,
        "full_range": [1, 1],
        "in_scope": [1, 1],
    }
    monkeypatch.setattr(
        fetch,
        "search_law",
        lambda title: {
            "bbbs": "test-bbbs",
            "title": title,
            "gbrq": "2026-01-01",
            "sxrq": "2026-01-01",
            "sxx": 3,
        },
    )

    def fake_download(bbbs, fmt):
        if fmt == "pdf":
            raise RuntimeError("下载地址获取失败 (pdf)")
        return b"fake-docx"

    monkeypatch.setattr(fetch, "download_file", fake_download)
    monkeypatch.setattr(
        fetch, "docx_paragraphs", lambda _: ["第一条　这是测试条文的正文内容，长度足够。"]
    )

    out_dir = tmp_path / "out"
    raw_dir = tmp_path / "raw"
    out_dir.mkdir()
    raw_dir.mkdir()
    entry = fetch.fetch_target(target, out_dir, raw_dir)
    assert entry["pdf_sha256"] == ""
    assert entry["count"] == 1
    assert (out_dir / "test.json").exists()
