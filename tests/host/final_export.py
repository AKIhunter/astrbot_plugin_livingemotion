"""Export generated acceptance evidence without runtime credentials or raw logs."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("runs", nargs="+", type=Path)
    args = parser.parse_args()
    target = Path(__file__).parent / "final_evidence"
    target.mkdir(exist_ok=True)
    for root in args.runs:
        report = json.loads((root / "report.json").read_text())
        # Hostname/machine identity is unnecessary for reproducibility.
        report.pop("platform", None)
        report["environment"] = "macOS arm64; temporary AstrBot root; synthetic identities only"
        report["run_id"] = root.name
        report["source_hashes"] = report.pop("source_before", report.get("source_hashes", {}))
        text = json.dumps(report, ensure_ascii=False, indent=2)
        if any(marker in text for marker in ("Bearer ", "eyJhbGci", "browser-ready", "/Users/")):
            raise ValueError("Evidence redaction check failed")
        destination = target / root.name
        destination.mkdir(exist_ok=True)
        (destination / "host.json").write_text(text)
        browser_path = root / "browser-evidence/results.json"
        if browser_path.exists():
            browser = json.loads(browser_path.read_text())
            (destination / "browser.json").write_text(json.dumps(browser, ensure_ascii=False, indent=2))
            for image in browser.get("screenshots", []):
                if Path(image).name != image or not image.endswith(".png"):
                    raise ValueError("Unexpected screenshot filename")
                shutil.copy2(root / "browser-evidence" / image, destination / image)
        manifest = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(destination.iterdir()) if p.name != "manifest.json"}
        (destination / "manifest.json").write_text(json.dumps(manifest, indent=2))
        print(json.dumps({"run": root.name, "counts": report["counts"], "files": len(manifest)}))


if __name__ == "__main__":
    main()
