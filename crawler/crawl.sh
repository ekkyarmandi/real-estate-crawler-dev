#!/bin/bash
cd /brixi/crawler
source /brixi/.venv/bin/activate
scrapy crawl halooglasi -s LOAD_EXISTING_URLS=False
scrapy crawl 4zida -s LOAD_EXISTING_URLS=False
scrapy crawl nekretnine -s LOAD_EXISTING_URLS=False
