TEI to ODF Converter

This project provides a Python script to convert PDFs to TEI (Text Encoding Initiative) format using GROBID and then generate ODT (OpenDocument Text) files from the TEI content with proper formatting. The script handles headings, lists, tables, and references.

Prerequisites

Anaconda or Miniconda installed.
Java 11 or higher (required for GROBID).
GROBID installed and running on http://localhost:8070.
Installation

Clone the Repository
git clone https://github.com/yourusername/your-repository.git
cd your-repository
Set Up the Conda Environment
Create and activate the conda environment:

conda create -n tei_to_odfenv python=3.8
conda activate tei_to_odf_env

Install Dependencies
pip install lxml odfpy requests

Ensure GROBID is installed and running.

Usage

Prepare Directories:
create
source/
tei/
output/
in the folder holding 
convert.py

Place your PDF files in the source/ directory.
The script will generate TEI files in the tei/ directory and ODF files in the output/ directory.

Run the Script:
python your_script_name.py
The script will:

Convert PDFs to TEI (if TEI files don't already exist).
Parse TEI files to extract content.
Generate ODF files with proper formatting.

Notes

GROBID Server URL: If GROBID is running on a different URL or port, update the convert_pdf_to_tei function in the script.
Dependencies: Ensure all dependencies are installed in your conda environment.
