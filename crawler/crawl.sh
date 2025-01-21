#!/bin/bash
cd /brixi/crawler
source /brixi/.venv/bin/activate
scrapy crawl halooglasi
scrapy crawl 4zida
scrapy crawl nekretnine
