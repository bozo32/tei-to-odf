import os
from pathlib import Path
import requests
import re
from lxml import etree
from odf.opendocument import OpenDocumentText
from odf.text import P, H, Span, A, BookmarkStart, BookmarkEnd
from odf.style import Style, TextProperties
from odf import table, text

# Paths
HOME_FOLDER = Path(__file__).parent
SOURCE_FOLDER = HOME_FOLDER / "source"
TEI_FOLDER = HOME_FOLDER / "tei"
OUTPUT_FOLDER = HOME_FOLDER / "output"

# GROBID server details
GROBID_URL = "http://localhost:8070/api/processFulltextDocument"

# Ensure necessary directories exist
TEI_FOLDER.mkdir(parents=True, exist_ok=True)
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

def log(message):
    """Simple logging function to print to console."""
    print(message)

def find_pdfs(directory):
    """Recursively find all PDFs in the given directory."""
    return list(directory.rglob("*.pdf"))

def convert_pdf_to_tei(pdf_path, tei_output_path):
    """Convert a single PDF to TEI using GROBID."""
    try:
        with open(pdf_path, "rb") as pdf_file:
            response = requests.post(
                GROBID_URL,
                files={"input": pdf_file},
                data={"teiCoordinates": "biblStruct"},
                timeout=120  # Adjust timeout as needed
            )
            response.raise_for_status()  # Raise HTTPError for bad responses
            tei_content = response.text
            with open(tei_output_path, "w", encoding="utf-8") as tei_file:
                tei_file.write(tei_content)
            log(f"Converted PDF to TEI: {pdf_path}")
            return tei_output_path
    except Exception as e:
        log(f"Error converting PDF to TEI ({pdf_path}): {e}")
        return None

def parse_tei(tei_file):
    """Parse TEI file to extract structured content."""
    try:
        tree = etree.parse(tei_file)
        ns = {"tei": "http://www.tei-c.org/ns/1.0"}

        # Extract title
        title = tree.xpath("//tei:titleStmt/tei:title[@type='main']", namespaces=ns)
        title_text = title[0].text if title else "N/A"

        # Extract authors
        authors = []
        for author in tree.xpath("//tei:sourceDesc//tei:author", namespaces=ns):
            name_parts = []
            persName = author.find('tei:persName', namespaces=ns)
            if persName is not None:
                forename = persName.find('tei:forename', namespaces=ns)
                surname = persName.find('tei:surname', namespaces=ns)
                if forename is not None:
                    name_parts.append(forename.text)
                if surname is not None:
                    name_parts.append(surname.text)
            full_name = ' '.join(name_parts)
            if full_name:
                authors.append(full_name)

        # Extract abstract
        abstract_elem = tree.xpath("//tei:profileDesc/tei:abstract", namespaces=ns)
        abstract_text = ''
        if abstract_elem:
            abstract_text = ''.join(abstract_elem[0].itertext()).strip()

        # Extract body content
        body = tree.xpath("//tei:text/tei:body", namespaces=ns)
        body_elements = []
        if body:
            # Process body content recursively
            def process_body_elements(parent):
                for elem in parent:
                    tag = etree.QName(elem).localname
                    if tag == 'head':
                        # Heading
                        heading_text = ''.join(elem.itertext()).strip()
                        body_elements.append({'type': 'heading', 'text': heading_text})
                    elif tag == 'p':
                        # Paragraph
                        paragraph_content = get_paragraph_content(elem)
                        body_elements.append({'type': 'paragraph', 'content': paragraph_content})
                    elif tag == 'div':
                        # Process contents of div recursively
                        process_body_elements(elem)
                    elif tag == 'figure' and elem.get('type') == 'table':
                        # Table
                        table_data = parse_table(elem)
                        body_elements.append({'type': 'table', 'content': table_data})
                    else:
                        # Handle other elements if necessary
                        pass

            process_body_elements(body[0])

        # Extract references
        bibliography = tree.xpath("//tei:back//tei:listBibl//tei:biblStruct", namespaces=ns)
        references = []
        for ref in bibliography:
            ref_id = ref.get("{http://www.w3.org/XML/1998/namespace}id", "ref_" + str(len(references) + 1))
            ref_text = ' '.join(ref.itertext()).strip()
            references.append({"id": ref_id, "text": ref_text})

        return {
            "title": title_text,
            "authors": authors,
            "abstract": abstract_text,
            "body_elements": body_elements,
            "references": references,
        }
    except Exception as e:
        log(f"Error parsing TEI file ({tei_file}): {e}")
        return None

def get_paragraph_content(paragraph_elem):
    content = []
    # Recursive function to process the paragraph content
    def recurse(node):
        # Add text before child elements
        if node.text:
            content.append({'type': 'text', 'text': node.text})
        for child in node:
            tag = etree.QName(child).localname
            if tag == 'ref' and child.get('type') == 'bibr':
                # In-text citation
                ref_text = ''.join(child.itertext())
                target = child.get('target', '').lstrip('#')
                content.append({'type': 'ref', 'text': ref_text, 'target': target})
                # Add any tail text after the ref
                if child.tail:
                    content.append({'type': 'text', 'text': child.tail})
            else:
                # Recursively process other child elements
                recurse(child)
                # Add any tail text after the child
                if child.tail:
                    content.append({'type': 'text', 'text': child.tail})
    recurse(paragraph_elem)
    return content

def parse_table(figure_elem):
    ns = {"tei": "http://www.tei-c.org/ns/1.0"}
    table_elem = figure_elem.find('tei:table', namespaces=ns)
    if table_elem is None:
        return None

    rows_data = []
    for row in table_elem.findall('.//tei:row', namespaces=ns):
        cells = []
        for cell in row.findall('tei:cell', namespaces=ns):
            cell_text = ''.join(cell.itertext()).strip()
            cells.append(cell_text)
        rows_data.append(cells)
    return rows_data

def create_odt(parsed_data, output_file):
    """Create a beautifully formatted ODT file with proper styles for headings, paragraphs, lists, and tables."""
    try:
        doc = OpenDocumentText()

        # Define Title Style
        title_style = Style(name="Title", family="paragraph")
        title_style.addElement(TextProperties(attributes={
            "fontsize": "24pt",
            "fontweight": "bold",
            "fontfamily": "Arial"
        }))
        doc.styles.addElement(title_style)

        # Define Author Style
        author_style = Style(name="AuthorStyle", family="paragraph")
        author_style.addElement(TextProperties(attributes={
            "fontsize": "12pt",
            "fontweight": "bold",
            "fontfamily": "Arial"
        }))
        doc.styles.addElement(author_style)

        # Define Abstract Style
        abstract_style = Style(name="AbstractStyle", family="paragraph")
        abstract_style.addElement(TextProperties(attributes={
            "fontsize": "12pt",
            "fontstyle": "italic",
            "fontfamily": "Arial"
        }))
        doc.styles.addElement(abstract_style)

        # Define Heading Style
        heading_style = Style(name="Heading", family="paragraph")
        heading_style.addElement(TextProperties(attributes={
            "fontsize": "18pt",
            "fontweight": "bold",
            "fontfamily": "Arial"
        }))
        doc.styles.addElement(heading_style)

        # Define Paragraph Style
        paragraph_style = Style(name="BodyText", family="paragraph")
        paragraph_style.addElement(TextProperties(attributes={
            "fontsize": "12pt",
            "fontfamily": "Arial",
        }))
        doc.styles.addElement(paragraph_style)

        # Add Title
        log("Adding title to the document")
        doc.text.addElement(P(stylename=title_style, text=parsed_data["title"]))

        # Add Authors
        if parsed_data["authors"]:
            authors_line = ', '.join(parsed_data["authors"])
            log(f"Adding authors: {authors_line}")
            doc.text.addElement(P(stylename=author_style, text=authors_line))

        # Add Abstract
        if parsed_data["abstract"]:
            log("Adding abstract to the document")
            doc.text.addElement(P(stylename=heading_style, text="Abstract"))
            doc.text.addElement(P(stylename=abstract_style, text=parsed_data["abstract"]))

        # Add Body Content
        for element in parsed_data['body_elements']:
            if element['type'] == 'heading':
                heading_text = element['text']
                log(f"Adding heading: {heading_text}")
                doc.text.addElement(P(stylename=heading_style, text=heading_text))
                doc.text.addElement(P(text=""))  # Add blank line after heading
            elif element['type'] == 'paragraph':
                paragraph = P(stylename=paragraph_style)
                for content_piece in element['content']:
                    if content_piece['type'] == 'text':
                        paragraph.addText(content_piece['text'])
                    elif content_piece['type'] == 'ref':
                        # Create hyperlink to the reference
                        ref_text = content_piece['text']
                        target = content_piece['target']
                        href = f"#{target}"
                        link = A(href=href, text=ref_text)
                        paragraph.addElement(link)
                    else:
                        # Handle other content types if necessary
                        pass
                doc.text.addElement(paragraph)
                doc.text.addElement(P(text=""))  # Add blank line after paragraph
            elif element['type'] == 'table':
                log("Adding table to the document")
                table_data = element['content']
                if table_data:
                    odt_table = table.Table()
                    for row_data in table_data:
                        odt_row = table.TableRow()
                        for cell_data in row_data:
                            odt_cell = table.TableCell()
                            cell_paragraph = P(stylename=paragraph_style, text=cell_data)
                            odt_cell.addElement(cell_paragraph)
                            odt_row.addElement(odt_cell)
                        odt_table.addElement(odt_row)
                    doc.text.addElement(odt_table)
                    doc.text.addElement(P(text=""))  # Blank line after table
            else:
                # Handle other element types if necessary
                pass

        # Add References Section
        if parsed_data["references"]:
            log("Adding references to the document")
            doc.text.addElement(P(text=""))  # Blank line before references heading
            doc.text.addElement(P(stylename=heading_style, text="References"))
            doc.text.addElement(P(text=""))  # Blank line after references heading

            for ref in parsed_data["references"]:
                try:
                    log(f"Adding reference: {ref['text'][:30]}...")  # Log part of the reference
                    reference = P(stylename=paragraph_style)
                    # Add a bookmark to the reference ID
                    reference.addElement(BookmarkStart(name=ref['id']))
                    reference.addText(f"{ref['text']} bibitem")
                    reference.addElement(BookmarkEnd(name=ref['id']))
                    doc.text.addElement(reference)
                    doc.text.addElement(P(text=""))  # Add blank line after each reference
                except Exception as e:
                    log(f"Error adding reference: {e}")

        # Save the ODT file
        log(f"Saving ODT file: {output_file}")
        doc.save(output_file)
        log(f"ODT file created: {output_file}")

    except Exception as e:
        log(f"Error creating ODT file: {e}")

def process_pdfs_to_odt():
    """Process all PDFs: convert to TEI if needed, then to ODT."""
    pdf_files = find_pdfs(SOURCE_FOLDER)
    log(f"Found {len(pdf_files)} PDF files in source folder.")

    for pdf_file in pdf_files:
        tei_file = TEI_FOLDER / f"{pdf_file.stem}.tei.xml"
        if tei_file.exists():  # Skip redundant conversions
            log(f"TEI file already exists for {pdf_file.name}, skipping conversion.")
        else:
            convert_pdf_to_tei(pdf_file, tei_file)

    # Process TEI files to create ODT files
    tei_files = TEI_FOLDER.glob("*.tei.xml")
    for tei_file in tei_files:
        parsed_data = parse_tei(tei_file)
        if parsed_data:
            output_file = OUTPUT_FOLDER / f"{tei_file.stem}.odt"
            if output_file.exists():
                log(f"ODT file already exists for {tei_file.name}, skipping ODT creation.")
                continue
            create_odt(parsed_data, output_file)

# Main execution
if __name__ == "__main__":
    process_pdfs_to_odt()
