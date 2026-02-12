#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
from pathlib import Path

import akshare as ak


def main() -> None:
    for key in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
        os.environ[key] = ""

    output_path = Path(__file__).resolve().parents[1] / "data" / "stock_zh_a_spot_em.txt"

    last_error: Exception | None = None
    df = None
    source_name = "stock_zh_a_spot_em"

    for attempt in range(5):
        try:
            df = ak.stock_zh_a_spot_em()
            break
        except Exception as error:
            last_error = error
            time.sleep(2 + attempt)

    if df is None:
        source_name = "stock_info_a_code_name"
        df = ak.stock_info_a_code_name()

    if "code" in df.columns and "name" in df.columns:
        df = df.rename(columns={"code": "代码", "name": "名称"})

    text = df.to_string(index=False)
    output_path.write_text(text, encoding="utf-8")

    print(f"导出完成: {output_path}")
    print(f"行数: {len(df)}")
    print(f"数据源: {source_name}")
    if last_error is not None and source_name != "stock_zh_a_spot_em":
        print(f"降级原因: {type(last_error).__name__}: {last_error}")


if __name__ == "__main__":
    main()
