export type WorkbookCell = string | number;
export type WorkbookRow = WorkbookCell[];

type WorkbookPart = {
  name: string;
  bytes: Uint8Array;
};

const ZIP_DATE = 33;
const ZIP_TIME = 0;
const textEncoder = new TextEncoder();

export function createSingleSheetXlsx(sheetName: string, rows: WorkbookRow[]): Uint8Array {
  const safeSheetName = sanitizeSheetName(sheetName);
  const parts: WorkbookPart[] = [
    part("[Content_Types].xml", contentTypesXml()),
    part("_rels/.rels", packageRelationshipsXml()),
    part("docProps/app.xml", appPropertiesXml(safeSheetName)),
    part("docProps/core.xml", corePropertiesXml()),
    part("xl/workbook.xml", workbookXml(safeSheetName)),
    part("xl/_rels/workbook.xml.rels", workbookRelationshipsXml()),
    part("xl/styles.xml", stylesXml()),
    part("xl/worksheets/sheet1.xml", worksheetXml(rows)),
  ];
  return buildZip(parts);
}

function part(name: string, content: string): WorkbookPart {
  return { name, bytes: textEncoder.encode(content) };
}

function buildZip(parts: WorkbookPart[]): Uint8Array {
  const localRecords: Uint8Array[] = [];
  const centralRecords: Uint8Array[] = [];
  let offset = 0;

  for (const workbookPart of parts) {
    const nameBytes = textEncoder.encode(workbookPart.name);
    const checksum = crc32(workbookPart.bytes);
    const localRecord = localFileRecord(nameBytes, workbookPart.bytes, checksum);
    const centralRecord = centralDirectoryRecord(
      nameBytes,
      workbookPart.bytes,
      checksum,
      offset,
    );
    localRecords.push(localRecord, workbookPart.bytes);
    centralRecords.push(centralRecord);
    offset += localRecord.length + workbookPart.bytes.length;
  }

  const centralDirectoryOffset = offset;
  const centralDirectorySize = centralRecords.reduce((total, record) => total + record.length, 0);
  const endRecord = endOfCentralDirectoryRecord(
    parts.length,
    centralDirectorySize,
    centralDirectoryOffset,
  );
  return concatenate([...localRecords, ...centralRecords, endRecord]);
}

function localFileRecord(
  nameBytes: Uint8Array,
  contentBytes: Uint8Array,
  checksum: number,
): Uint8Array {
  const record = new Uint8Array(30 + nameBytes.length);
  const view = new DataView(record.buffer);
  view.setUint32(0, 0x04034b50, true);
  view.setUint16(4, 20, true);
  view.setUint16(6, 0, true);
  view.setUint16(8, 0, true);
  view.setUint16(10, ZIP_TIME, true);
  view.setUint16(12, ZIP_DATE, true);
  view.setUint32(14, checksum, true);
  view.setUint32(18, contentBytes.length, true);
  view.setUint32(22, contentBytes.length, true);
  view.setUint16(26, nameBytes.length, true);
  view.setUint16(28, 0, true);
  record.set(nameBytes, 30);
  return record;
}

function centralDirectoryRecord(
  nameBytes: Uint8Array,
  contentBytes: Uint8Array,
  checksum: number,
  localRecordOffset: number,
): Uint8Array {
  const record = new Uint8Array(46 + nameBytes.length);
  const view = new DataView(record.buffer);
  view.setUint32(0, 0x02014b50, true);
  view.setUint16(4, 20, true);
  view.setUint16(6, 20, true);
  view.setUint16(8, 0, true);
  view.setUint16(10, 0, true);
  view.setUint16(12, ZIP_TIME, true);
  view.setUint16(14, ZIP_DATE, true);
  view.setUint32(16, checksum, true);
  view.setUint32(20, contentBytes.length, true);
  view.setUint32(24, contentBytes.length, true);
  view.setUint16(28, nameBytes.length, true);
  view.setUint16(30, 0, true);
  view.setUint16(32, 0, true);
  view.setUint16(34, 0, true);
  view.setUint16(36, 0, true);
  view.setUint32(38, 0, true);
  view.setUint32(42, localRecordOffset, true);
  record.set(nameBytes, 46);
  return record;
}

function endOfCentralDirectoryRecord(
  entryCount: number,
  centralDirectorySize: number,
  centralDirectoryOffset: number,
): Uint8Array {
  const record = new Uint8Array(22);
  const view = new DataView(record.buffer);
  view.setUint32(0, 0x06054b50, true);
  view.setUint16(4, 0, true);
  view.setUint16(6, 0, true);
  view.setUint16(8, entryCount, true);
  view.setUint16(10, entryCount, true);
  view.setUint32(12, centralDirectorySize, true);
  view.setUint32(16, centralDirectoryOffset, true);
  view.setUint16(20, 0, true);
  return record;
}

function concatenate(chunks: Uint8Array[]): Uint8Array {
  const totalLength = chunks.reduce((total, chunk) => total + chunk.length, 0);
  const output = new Uint8Array(totalLength);
  let offset = 0;
  for (const chunk of chunks) {
    output.set(chunk, offset);
    offset += chunk.length;
  }
  return output;
}

function crc32(bytes: Uint8Array): number {
  let crc = 0xffffffff;
  for (const byte of bytes) {
    crc = (crc >>> 8) ^ CRC32_TABLE[(crc ^ byte) & 0xff];
  }
  return (crc ^ 0xffffffff) >>> 0;
}

const CRC32_TABLE = Array.from({ length: 256 }, (_, index) => {
  let value = index;
  for (let bit = 0; bit < 8; bit += 1) {
    value = value & 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1;
  }
  return value >>> 0;
});

function worksheetXml(rows: WorkbookRow[]): string {
  const columnCount = Math.max(1, ...rows.map((row) => row.length));
  const dimension = `A1:${cellReference(columnCount - 1, Math.max(rows.length, 1))}`;
  const renderedRows = rows.map((row, index) => rowXml(index + 1, row)).join("\n");
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <dimension ref="${dimension}"/>
  <sheetViews>
    <sheetView workbookViewId="0"/>
  </sheetViews>
  <sheetFormatPr defaultRowHeight="15"/>
  <sheetData>
${renderedRows}
  </sheetData>
  <pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" header="0.3" footer="0.3"/>
</worksheet>
`;
}

function rowXml(rowNumber: number, row: WorkbookRow): string {
  if (row.length === 0) {
    return `    <row r="${rowNumber}"/>`;
  }
  const cells = row.map((value, columnIndex) => cellXml(cellReference(columnIndex, rowNumber), value)).join("");
  return `    <row r="${rowNumber}">${cells}</row>`;
}

function cellXml(reference: string, value: WorkbookCell): string {
  if (typeof value === "number") {
    return `<c r="${reference}"><v>${value}</v></c>`;
  }
  return `<c r="${reference}" t="inlineStr"><is><t>${escapeXml(value)}</t></is></c>`;
}

function cellReference(columnIndex: number, rowNumber: number): string {
  return `${columnName(columnIndex)}${rowNumber}`;
}

function columnName(columnIndex: number): string {
  let value = columnIndex;
  let name = "";
  do {
    const remainder = value % 26;
    name = `${String.fromCharCode(65 + remainder)}${name}`;
    value = Math.floor(value / 26) - 1;
  } while (value >= 0);
  return name;
}

function sanitizeSheetName(sheetName: string): string {
  const cleaned = sheetName.replace(/[\]\\/*?:[\]]/g, " ").trim();
  return escapeXml((cleaned || "Sheet1").slice(0, 31));
}

function escapeXml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function contentTypesXml(): string {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>
`;
}

function packageRelationshipsXml(): string {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
`;
}

function workbookXml(sheetName: string): string {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="${sheetName}" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>
`;
}

function workbookRelationshipsXml(): string {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>
`;
}

function stylesXml(): string {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>
  <fills count="1"><fill><patternFill patternType="none"/></fill></fills>
  <borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>
`;
}

function appPropertiesXml(sheetName: string): string {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>boatraceCal</Application>
  <DocSecurity>0</DocSecurity>
  <ScaleCrop>false</ScaleCrop>
  <HeadingPairs>
    <vt:vector size="2" baseType="variant">
      <vt:variant><vt:lpstr>Worksheets</vt:lpstr></vt:variant>
      <vt:variant><vt:i4>1</vt:i4></vt:variant>
    </vt:vector>
  </HeadingPairs>
  <TitlesOfParts>
    <vt:vector size="1" baseType="lpstr">
      <vt:lpstr>${sheetName}</vt:lpstr>
    </vt:vector>
  </TitlesOfParts>
</Properties>
`;
}

function corePropertiesXml(): string {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:creator>boatraceCal</dc:creator>
  <cp:lastModifiedBy>boatraceCal</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">1980-01-01T00:00:00Z</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">1980-01-01T00:00:00Z</dcterms:modified>
</cp:coreProperties>
`;
}
