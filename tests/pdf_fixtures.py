"""PDF sintéticos en memoria para comprobar extracción sin documentos personales."""
from io import BytesIO
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject


def make_pdf(pages=("Texto de prueba en español.",), *, password=None):
    writer = PdfWriter()
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                             NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica"),
                             NameObject("/Encoding"): NameObject("/WinAnsiEncoding")})
    for text in pages:
        page = writer.add_blank_page(width=595, height=842)
        contents = DecodedStreamObject()
        if text is not None:
            page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
            encoded = text.encode("cp1252").hex()
            contents.set_data(f"BT /F1 12 Tf 72 720 Td <{encoded}> Tj ET".encode("ascii"))
        else:
            # Página que solo contiene una imagen, como un escaneo sin OCR.
            image = DecodedStreamObject()
            image.set_data(b"\x00\x00\x00")
            image.update({NameObject("/Type"): NameObject("/XObject"),
                          NameObject("/Subtype"): NameObject("/Image"),
                          NameObject("/Width"): NumberObject(1), NameObject("/Height"): NumberObject(1),
                          NameObject("/ColorSpace"): NameObject("/DeviceRGB"),
                          NameObject("/BitsPerComponent"): NumberObject(8)})
            page[NameObject("/Resources")] = DictionaryObject({NameObject("/XObject"): DictionaryObject({NameObject("/Im1"): writer._add_object(image)})})
            contents.set_data(b"q 300 0 0 300 72 400 cm /Im1 Do Q")
        page[NameObject("/Contents")] = writer._add_object(contents)
    if password:
        writer.encrypt(password)
    stream = BytesIO()
    writer.write(stream)
    return stream.getvalue()
