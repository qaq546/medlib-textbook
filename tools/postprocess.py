# -*- coding: utf-8 -*-
"""postprocess.py — 教材分片 md 后处理流水线驱动(通用模板版)。

把 MinerU 转换出的分片 md 依次跑完五个阶段:
  1) fix-tables.py          表格专项修复(合并单元格转 HTML、圈号、上下标、表题加粗)
                            [本书数据内嵌,模板版数据区为空;按 specs/README 填写]
  2) verify-tables.py       表格结构校验(rowspan/colspan、GFM 列数、残留检查)
  3) backfill-punct.py      按 PDF 文本层回填行拼接丢失的标点(安全模式)
  4) audit-para.py          段落级严格包含审计
  5) audit-para-lenient.py  括号归一审计(区分标点型/内容型差异)

用法:
  python postprocess.py --md <md 文件> --pages <PDF 逐页 txt 目录> [--work <输出目录>] [--apply-backfill]

说明:
  - 同一本书用相同 MinerU 模型版本重新转换,输出确定性 → 同样错误会重现,
    本流水线可对新的输出文件直接重跑并修复(内容定位,不依赖行号)。
  - 换书:fix-tables / verify-tables 的本书数据区需按新书 PDF 文本层重写(见 specs/README.md);
    backfill-punct / audit-para* 为通用阶段,直接可用。
"""
import io, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MD = r"<md 文件路径>"
DEFAULT_PAGES = r"<PDF 逐页 txt 目录>"
DEFAULT_WORK = r"<输出目录,如 work>"


def arg(name, default):
    if name in sys.argv:
        return sys.argv[sys.argv.index(name) + 1]
    return default


def run(script, extra=None):
    py = sys.executable
    cmd = [py, os.path.join(HERE, script)]
    if extra:
        cmd += extra
    print("\n===== %s =====" % script, flush=True)
    r = subprocess.run(cmd, cwd=HERE)
    return r.returncode


def main():
    md = arg("--md", DEFAULT_MD)
    pages = arg("--pages", DEFAULT_PAGES)
    work = arg("--work", DEFAULT_WORK)
    apply_backfill = "--apply-backfill" in sys.argv

    print("md   =", md)
    print("pages=", pages)
    print("work =", work)
    print("apply_backfill =", apply_backfill)

    results = {}
    results["fix-tables"] = run("fix-tables.py", ["--md", md])
    results["verify-tables"] = run("verify-tables.py", ["--md", md])
    results["backfill-punct"] = run("backfill-punct.py", ["--md", md, "--pages", pages, "--work", work])
    results["audit-para"] = run("audit-para.py", ["--md", md, "--pages", pages, "--work", work])
    results["audit-para-lenient"] = run("audit-para-lenient.py", ["--md", md, "--pages", pages, "--work", work])

    backfilled = os.path.join(work, os.path.basename(md).replace(".md", "-backfilled.md"))
    if apply_backfill and results["backfill-punct"] == 0 and os.path.exists(backfilled):
        import shutil
        shutil.copyfile(backfilled, md)
        print("\n[postprocess] --apply-backfill: 已将 %s 覆盖回 %s" % (os.path.basename(backfilled), md))

    print("\n===== 汇总 =====")
    ok = True
    for name, code in results.items():
        mark = "OK " if code == 0 else "FAIL(%d)" % code
        print("  %-16s %s" % (name, mark))
        if code != 0:
            ok = False
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
