.PHONY: demo test docker-build

demo:
	copyspace-guard analyze --csv examples/ring15.csv --bw 256 --roi examples/roi.yml --outdir artifacts/demo

test:
	python -m compileall -q src
	python -m unittest discover -s tests -v
	copyspace-guard analyze --csv examples/ring15.csv --bw 256 --roi examples/roi.yml --outdir artifacts/demo
	copyspace-guard gate artifacts/demo/summary.json --config examples/copyspace_guard.yml

docker-build:
	docker build -t copyspace-guard .
