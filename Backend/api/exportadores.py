# api/exportadores.py
# ==============================================================================
# REPORTES (funcionalidad adicional) — Exportación a 3 formatos (PDF, Excel y CSV)
#
# Se implementan con la librería estándar de Python (zipfile, csv, io) para no
# agregar dependencias nuevas al despliegue:
#   - PDF  : documento PDF 1.4 con tabla paginada (A4 horizontal, Helvetica).
#   - XLSX : libro de Excel (Office Open XML) con encabezado en negrita.
#   - CSV  : texto separado por ';' con BOM UTF-8 (abre bien en Excel en español).
# ==============================================================================
import csv
import io
import zipfile
from datetime import datetime
from xml.sax.saxutils import escape

from django.http import HttpResponse


def _texto(valor):
    if valor is None:
        return ''
    if isinstance(valor, bool):
        return 'Sí' if valor else 'No'
    return str(valor)


# ------------------------------------------------------------------------------
# CSV
# ------------------------------------------------------------------------------
def generar_csv(titulo, columnas, filas):
    salida = io.StringIO()
    salida.write('﻿')
    writer = csv.writer(salida, delimiter=';')
    writer.writerow([titulo])
    writer.writerow([f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"])
    writer.writerow([])
    writer.writerow([c['titulo'] for c in columnas])
    for fila in filas:
        writer.writerow([_texto(fila.get(c['clave'])) for c in columnas])
    return salida.getvalue().encode('utf-8')


# ------------------------------------------------------------------------------
# XLSX (Office Open XML mínimo)
# ------------------------------------------------------------------------------
def _col_letra(indice):
    letras = ''
    indice += 1
    while indice:
        indice, resto = divmod(indice - 1, 26)
        letras = chr(65 + resto) + letras
    return letras


def _celda(ref, valor, estilo=0):
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return f'<c r="{ref}" s="{estilo}"><v>{valor}</v></c>'
    try:
        from decimal import Decimal
        if isinstance(valor, Decimal):
            return f'<c r="{ref}" s="{estilo}"><v>{valor}</v></c>'
    except Exception:  # pragma: no cover
        pass
    texto = escape(_texto(valor))
    return f'<c r="{ref}" t="inlineStr" s="{estilo}"><is><t xml:space="preserve">{texto}</t></is></c>'


def generar_xlsx(titulo, columnas, filas):
    filas_xml = []
    filas_xml.append(f'<row r="1">{_celda("A1", titulo, 1)}</row>')
    filas_xml.append(
        f'<row r="2">{_celda("A2", "Generado: " + datetime.now().strftime("%d/%m/%Y %H:%M"))}</row>'
    )
    encabezado = ''.join(
        _celda(f'{_col_letra(i)}4', c['titulo'], 2) for i, c in enumerate(columnas)
    )
    filas_xml.append(f'<row r="4">{encabezado}</row>')
    for n, fila in enumerate(filas, start=5):
        celdas = ''.join(
            _celda(f'{_col_letra(i)}{n}', fila.get(c['clave'])) for i, c in enumerate(columnas)
        )
        filas_xml.append(f'<row r="{n}">{celdas}</row>')

    anchos = ''.join(
        f'<col min="{i + 1}" max="{i + 1}" width="{max(12, min(45, len(c["titulo"]) + 6))}" customWidth="1"/>'
        for i, c in enumerate(columnas)
    )
    hoja = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<cols>{anchos}</cols><sheetData>{"".join(filas_xml)}</sheetData></worksheet>'
    )
    estilos = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="3"><font><sz val="11"/><name val="Calibri"/></font>'
        '<font><b/><sz val="14"/><name val="Calibri"/></font>'
        '<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font></fonts>'
        '<fills count="3"><fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FF1F2937"/></patternFill></fill></fills>'
        '<borders count="1"><border/></borders>'
        '<cellStyleXfs count="1"><xf/></cellStyleXfs>'
        '<cellXfs count="3"><xf fontId="0"/><xf fontId="1" applyFont="1"/>'
        '<xf fontId="2" fillId="2" applyFont="1" applyFill="1"/></cellXfs>'
        '</styleSheet>'
    )
    nombre_hoja = escape(titulo[:31].replace('/', '-').replace(':', ' ')) or 'Reporte'
    libro = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets><sheet name="{nombre_hoja}" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    tipos = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '</Types>'
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>'
    )
    libro_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        '</Relationships>'
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', tipos)
        z.writestr('_rels/.rels', rels)
        z.writestr('xl/workbook.xml', libro)
        z.writestr('xl/_rels/workbook.xml.rels', libro_rels)
        z.writestr('xl/styles.xml', estilos)
        z.writestr('xl/worksheets/sheet1.xml', hoja)
    return buffer.getvalue()


# ------------------------------------------------------------------------------
# PDF (escrito a mano, PDF 1.4, fuente estándar Helvetica con WinAnsiEncoding)
# ------------------------------------------------------------------------------
_ANCHO, _ALTO = 842, 595  # A4 horizontal en puntos
_MARGEN = 36


def _pdf_esc(texto):
    texto = texto.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
    return texto.encode('cp1252', errors='replace').decode('latin-1')


def _recortar(texto, ancho_pt, tam):
    max_chars = max(3, int(ancho_pt / (tam * 0.5)))
    return texto if len(texto) <= max_chars else texto[: max_chars - 1] + '…'


def generar_pdf(titulo, columnas, filas, subtitulo=''):
    tam = 8
    alto_fila = 14
    util = _ANCHO - 2 * _MARGEN

    # Ancho proporcional a la longitud típica de cada columna.
    pesos = []
    for c in columnas:
        muestra = [len(_texto(f.get(c['clave']))) for f in filas[:200]] or [0]
        pesos.append(max(len(c['titulo']), min(40, max(muestra))) + 2)
    total = sum(pesos) or 1
    anchos = [util * p / total for p in pesos]

    filas_por_pagina = int((_ALTO - 2 * _MARGEN - 70) / alto_fila)
    paginas_datos = [filas[i:i + filas_por_pagina] for i in range(0, len(filas), filas_por_pagina)] or [[]]
    fecha = datetime.now().strftime('%d/%m/%Y %H:%M')

    contenidos = []
    for num, bloque in enumerate(paginas_datos, start=1):
        ops = []
        y = _ALTO - _MARGEN
        ops.append(f'BT /F2 15 Tf {_MARGEN} {y - 12} Td (PORKY GYM - {_pdf_esc(titulo)}) Tj ET')
        texto_sub = subtitulo or 'Sistema de Información Porky Gym'
        ops.append(f'BT /F1 9 Tf {_MARGEN} {y - 28} Td ({_pdf_esc(texto_sub)}) Tj ET')
        ops.append(
            f'BT /F1 9 Tf {_ANCHO - _MARGEN - 190} {y - 28} Td '
            f'({_pdf_esc(f"Generado: {fecha}  -  Pág. {num}/{len(paginas_datos)}")}) Tj ET'
        )
        y -= 50
        # Encabezado de tabla
        ops.append(f'0.12 0.16 0.22 rg {_MARGEN} {y - alto_fila + 3} {util} {alto_fila} re f')
        x = _MARGEN
        ops.append('1 1 1 rg')
        for c, w in zip(columnas, anchos):
            ops.append(f'BT /F2 {tam} Tf {x + 3:.1f} {y - 7:.1f} Td ({_pdf_esc(_recortar(c["titulo"], w - 6, tam))}) Tj ET')
            x += w
        ops.append('0 0 0 rg')
        y -= alto_fila
        for i, fila in enumerate(bloque):
            if i % 2 == 0:
                ops.append(f'0.95 0.95 0.95 rg {_MARGEN} {y - alto_fila + 3} {util} {alto_fila} re f 0 0 0 rg')
            x = _MARGEN
            for c, w in zip(columnas, anchos):
                valor = _recortar(_texto(fila.get(c['clave'])), w - 6, tam)
                ops.append(f'BT /F1 {tam} Tf {x + 3:.1f} {y - 7:.1f} Td ({_pdf_esc(valor)}) Tj ET')
                x += w
            y -= alto_fila
        if not bloque:
            ops.append(f'BT /F1 10 Tf {_MARGEN} {y - 12} Td (Sin registros para los filtros seleccionados.) Tj ET')
        if num == len(paginas_datos):
            ops.append(f'BT /F2 9 Tf {_MARGEN} {_MARGEN - 10} Td (Total de registros: {len(filas)}) Tj ET')
        contenidos.append('\n'.join(ops).encode('latin-1'))

    objetos = []  # lista de bytes, índice 0 -> objeto 1

    def agregar(cuerpo):
        objetos.append(cuerpo)
        return len(objetos)

    cat = agregar(b'')  # placeholder catálogo
    pags = agregar(b'')  # placeholder páginas
    f1 = agregar(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>')
    f2 = agregar(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>')
    ids_paginas = []
    for contenido in contenidos:
        cid = agregar(b'<< /Length %d >>\nstream\n' % len(contenido) + contenido + b'\nendstream')
        pid = agregar(
            (f'<< /Type /Page /Parent {pags} 0 R /MediaBox [0 0 {_ANCHO} {_ALTO}] '
             f'/Resources << /Font << /F1 {f1} 0 R /F2 {f2} 0 R >> >> /Contents {cid} 0 R >>').encode()
        )
        ids_paginas.append(pid)
    objetos[cat - 1] = f'<< /Type /Catalog /Pages {pags} 0 R >>'.encode()
    kids = ' '.join(f'{p} 0 R' for p in ids_paginas)
    objetos[pags - 1] = f'<< /Type /Pages /Kids [{kids}] /Count {len(ids_paginas)} >>'.encode()

    salida = io.BytesIO()
    salida.write(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
    offsets = []
    for i, cuerpo in enumerate(objetos, start=1):
        offsets.append(salida.tell())
        salida.write(f'{i} 0 obj\n'.encode() + cuerpo + b'\nendobj\n')
    inicio_xref = salida.tell()
    salida.write(f'xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n'.encode())
    for off in offsets:
        salida.write(f'{off:010d} 00000 n \n'.encode())
    salida.write(f'trailer\n<< /Size {len(objetos) + 1} /Root {cat} 0 R >>\nstartxref\n{inicio_xref}\n%%EOF'.encode())
    return salida.getvalue()


# ------------------------------------------------------------------------------
# Respuesta HTTP según el formato pedido
# ------------------------------------------------------------------------------
FORMATOS = {
    'pdf': ('application/pdf', 'pdf'),
    'xlsx': ('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'xlsx'),
    'csv': ('text/csv; charset=utf-8', 'csv'),
}


def respuesta_archivo(formato, nombre_base, titulo, columnas, filas, subtitulo=''):
    if formato == 'pdf':
        contenido = generar_pdf(titulo, columnas, filas, subtitulo)
    elif formato == 'xlsx':
        contenido = generar_xlsx(titulo, columnas, filas)
    else:
        formato = 'csv'
        contenido = generar_csv(titulo, columnas, filas)
    tipo, ext = FORMATOS[formato]
    respuesta = HttpResponse(contenido, content_type=tipo)
    nombre = f"{nombre_base}_{datetime.now().strftime('%Y%m%d_%H%M')}.{ext}"
    respuesta['Content-Disposition'] = f'attachment; filename="{nombre}"'
    respuesta['Access-Control-Expose-Headers'] = 'Content-Disposition'
    return respuesta
