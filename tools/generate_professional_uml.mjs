import fs from "fs";
import path from "path";
import { createRequire } from "module";

const require = createRequire(import.meta.url);
const sharp = require("C:/Users/cl183288210/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp/dist/index.cjs");

const root = process.cwd();
const workDir = path.join(root, "_docx_work", "pro_uml_svg");
const outDir = path.join(root, "diagramas_uml_profesionales");
fs.mkdirSync(workDir, { recursive: true });
fs.mkdirSync(outDir, { recursive: true });

const C = {
  navy: "#153A5B",
  blue: "#2F6690",
  sky: "#E6F0F7",
  pale: "#F7FAFC",
  ink: "#17202A",
  muted: "#5D6D7E",
  line: "#AEBAC5",
  orange: "#E99A3A",
  orangePale: "#FFF3E3",
  green: "#2A7F62",
  greenPale: "#E6F4EF",
  white: "#FFFFFF",
};

const esc = (s) => String(s).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");

function defs() {
  return `<defs>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="4" stdDeviation="5" flood-color="#153A5B" flood-opacity="0.12"/>
    </filter>
    <marker id="arrow" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto" markerUnits="strokeWidth">
      <path d="M0,0 L9,4.5 L0,9 z" fill="${C.blue}"/>
    </marker>
    <marker id="openArrow" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto" markerUnits="strokeWidth">
      <path d="M1,1 L9,5 L1,9" fill="none" stroke="${C.blue}" stroke-width="1.5"/>
    </marker>
    <marker id="diamond" markerWidth="16" markerHeight="12" refX="14" refY="6" orient="auto">
      <path d="M0,6 L7,1 L14,6 L7,11 z" fill="${C.white}" stroke="${C.blue}" stroke-width="1.5"/>
    </marker>
  </defs>`;
}

function base(title, subtitle, body) {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900">
    ${defs()}
    <rect width="1600" height="900" fill="${C.white}"/>
    <rect x="0" y="0" width="1600" height="12" fill="${C.navy}"/>
    <text x="76" y="70" font-family="Segoe UI, Arial" font-size="34" font-weight="700" fill="${C.navy}">${esc(title)}</text>
    <text x="76" y="103" font-family="Segoe UI, Arial" font-size="17" fill="${C.muted}">${esc(subtitle)}</text>
    <line x1="76" y1="126" x2="1524" y2="126" stroke="${C.line}" stroke-width="1.5"/>
    ${body}
    <line x1="76" y1="842" x2="1524" y2="842" stroke="${C.line}" stroke-width="1"/>
    <text x="76" y="872" font-family="Segoe UI, Arial" font-size="14" fill="${C.muted}">Operations Analytics</text>
    <text x="1524" y="872" text-anchor="end" font-family="Segoe UI, Arial" font-size="14" fill="${C.muted}">Proyecto Capstone 2026</text>
  </svg>`;
}

function textLines(x, y, lines, {size=18, fill=C.ink, weight=400, anchor="start", lineHeight=24, italic=false}={}) {
  const spans = lines.map((line, i) => `<tspan x="${x}" dy="${i === 0 ? 0 : lineHeight}">${esc(line)}</tspan>`).join("");
  return `<text x="${x}" y="${y}" text-anchor="${anchor}" font-family="Segoe UI, Arial" font-size="${size}" font-weight="${weight}" font-style="${italic ? "italic" : "normal"}" fill="${fill}">${spans}</text>`;
}

function roundedBox(x, y, w, h, title, lines=[], {fill=C.pale, stroke=C.blue, titleFill=C.sky, titleSize=18, textSize=15, radius=12, shadow=true, stereotype=""}={}) {
  const titleY = stereotype ? y + 26 : y + 32;
  const title2Y = stereotype ? y + 49 : y + 32;
  const headH = stereotype ? 68 : 52;
  return `<g ${shadow ? 'filter="url(#shadow)"' : ""}>
    <rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${radius}" fill="${fill}" stroke="${stroke}" stroke-width="2"/>
    <path d="M${x+radius},${y} H${x+w-radius} Q${x+w},${y} ${x+w},${y+radius} V${y+headH} H${x} V${y+radius} Q${x},${y} ${x+radius},${y} Z" fill="${titleFill}"/>
    ${stereotype ? textLines(x+w/2, titleY, [stereotype], {size:12, fill:C.muted, anchor:"middle", italic:true}) : ""}
    ${textLines(x+w/2, title2Y, [title], {size:titleSize, fill:C.navy, weight:700, anchor:"middle"})}
    ${lines.length ? textLines(x+18, y+headH+28, lines, {size:textSize, fill:C.ink, lineHeight:textSize+8}) : ""}
  </g>`;
}

function pathLine(d, {dash=false, marker="arrow", color=C.blue, width=2}={}) {
  return `<path d="${d}" fill="none" stroke="${color}" stroke-width="${width}" ${dash ? 'stroke-dasharray="8 7"' : ""} marker-end="url(#${marker})"/>
  `;
}

function label(x, y, value, {size=13, fill=C.muted, bg=C.white}={}) {
  const width = Math.max(40, value.length * size * 0.58 + 16);
  return `<g><rect x="${x-width/2}" y="${y-size}" width="${width}" height="${size+7}" rx="5" fill="${bg}"/><text x="${x}" y="${y}" text-anchor="middle" font-family="Segoe UI, Arial" font-size="${size}" fill="${fill}">${esc(value)}</text></g>`;
}

function actor(x, y, title) {
  return `<g>
    <circle cx="${x}" cy="${y}" r="22" fill="${C.white}" stroke="${C.navy}" stroke-width="3"/>
    <line x1="${x}" y1="${y+22}" x2="${x}" y2="${y+91}" stroke="${C.navy}" stroke-width="3"/>
    <line x1="${x-40}" y1="${y+48}" x2="${x+40}" y2="${y+48}" stroke="${C.navy}" stroke-width="3"/>
    <line x1="${x}" y1="${y+91}" x2="${x-35}" y2="${y+145}" stroke="${C.navy}" stroke-width="3"/>
    <line x1="${x}" y1="${y+91}" x2="${x+35}" y2="${y+145}" stroke="${C.navy}" stroke-width="3"/>
    ${textLines(x, y+179, title.split("\n"), {size:17, weight:600, anchor:"middle", lineHeight:21})}
  </g>`;
}

function useCases() {
  const body = `
    <rect x="340" y="164" width="910" height="630" rx="18" fill="${C.pale}" stroke="${C.navy}" stroke-width="2.5"/>
    <rect x="340" y="164" width="910" height="54" rx="18" fill="${C.navy}"/>
    <rect x="340" y="198" width="910" height="20" fill="${C.navy}"/>
    <text x="795" y="199" text-anchor="middle" font-family="Segoe UI, Arial" font-size="21" font-weight="700" fill="white">Operations Analytics</text>
    ${actor(180, 278, "Programador\nde tareas")}
    ${actor(180, 555, "Analista\nautorizado")}
    ${roundedBox(560, 270, 470, 100, "Ejecutar actualización automática FBL1N", [], {fill:C.white,titleFill:C.sky,shadow:false,titleSize:18,radius:50})}
    ${roundedBox(560, 445, 470, 100, "Consultar resultados y trazabilidad", [], {fill:C.white,titleFill:C.sky,shadow:false,titleSize:18,radius:50})}
    ${roundedBox(560, 620, 470, 100, "Administrar configuración y catálogos", [], {fill:C.white,titleFill:C.sky,shadow:false,titleSize:18,radius:50})}
    ${roundedBox(1320, 225, 205, 88, "SAP GUI", ["FBL1N"], {fill:C.orangePale,stroke:C.orange,titleFill:C.orangePale,shadow:false,titleSize:17,textSize:14})}
    ${roundedBox(1320, 410, 205, 96, "SharePoint", ["OneDrive"], {fill:C.orangePale,stroke:C.orange,titleFill:C.orangePale,shadow:false,titleSize:17,textSize:14})}
    ${roundedBox(1320, 600, 205, 88, "Outlook", ["Notificación"], {fill:C.orangePale,stroke:C.orange,titleFill:C.orangePale,shadow:false,titleSize:17,textSize:14})}
    <path d="M220,326 L560,320" stroke="${C.blue}" stroke-width="2.2" fill="none"/>
    <path d="M220,603 L560,495" stroke="${C.blue}" stroke-width="2.2" fill="none"/>
    <path d="M220,603 L560,670" stroke="${C.blue}" stroke-width="2.2" fill="none"/>
    ${pathLine("M1030,320 H1180 V269 H1320", {dash:true})}
    ${pathLine("M1030,495 H1320", {dash:true})}
    ${pathLine("M1030,320 H1180 V644 H1320", {dash:true})}
    ${label(1180, 252, "integración")}${label(1170, 480, "integración")}${label(1180, 627, "notificación")}
  `;
  return base("Diagrama de Casos de Uso", "Alcance funcional principal y actores del sistema", body);
}

function entity(x,y,w,title,fields,{color=C.blue,head=C.sky}={}) {
  const h = 64 + fields.length*30 + 18;
  return {h, svg:`<g filter="url(#shadow)"><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="8" fill="white" stroke="${color}" stroke-width="2"/><rect x="${x}" y="${y}" width="${w}" height="54" rx="8" fill="${head}"/><rect x="${x}" y="${y+44}" width="${w}" height="10" fill="${head}"/>${textLines(x+w/2,y+35,[title],{size:18,weight:700,anchor:"middle",fill:C.navy})}${fields.map((f,i)=>textLines(x+18,y+83+i*30,[f],{size:14,fill:i===0?C.navy:C.ink,weight:i===0?600:400})).join("")}</g>`};
}

function dataModel() {
  const tx=entity(95,235,350,"TransaccionFBL1N",["PK  documento","FK  sociedad_codigo","FK  moneda_codigo","FK  concepto_patron","importe","fecha_compensacion"]);
  const soc=entity(580,205,265,"Sociedad",["PK  codigo","nombre"]);
  const mon=entity(580,430,265,"Moneda",["PK  codigo","descripcion"]);
  const con=entity(580,655,265,"Concepto",["PK  patron","clasificacion"]);
  const run=entity(1030,230,300,"Ejecucion",["PK  sha256","inicio","estado","filas","duracion"]);
  const art=entity(1030,585,300,"Artefacto",["PK  ruta","tipo","fecha","publicado"]);
  const body=`${tx.svg}${soc.svg}${mon.svg}${con.svg}${run.svg}${art.svg}
    <path d="M445,305 H515 V265 H580" stroke="${C.blue}" stroke-width="2" fill="none"/>
    <path d="M445,350 H500 V490 H580" stroke="${C.blue}" stroke-width="2" fill="none"/>
    <path d="M445,395 H485 V715 H580" stroke="${C.blue}" stroke-width="2" fill="none"/>
    <path d="M1030,355 H920 V360 H445" stroke="${C.blue}" stroke-width="2" fill="none"/>
    <path d="M1180,459 V585" stroke="${C.blue}" stroke-width="2" fill="none"/>
    ${label(480,288,"N")}${label(560,248,"1")}${label(480,472,"N")}${label(560,473,"1")}${label(480,697,"N")}${label(560,698,"1")}
    ${label(780,342,"procesa")}${label(1003,342,"1")}${label(460,342,"N")}${label(1205,535,"1 : N")}
    <g><rect x="1380" y="265" width="150" height="94" rx="9" fill="${C.greenPale}" stroke="${C.green}" stroke-width="1.8"/>${textLines(1455,297,["Persistencia"],{size:15,weight:700,anchor:"middle",fill:C.green})}${textLines(1455,324,["Excel + JSON"],{size:14,anchor:"middle"})}</g>
    ${pathLine("M1380,312 H1330", {dash:true,color:C.green})}
  `;
  return base("Modelo Lógico de Datos", "Entidades persistidas en archivos Excel y estados JSON", body);
}

function umlClass(x,y,w,title,attrs,ops,{stereo=""}={}) {
  const row=25, head=stereo?72:52, h=head+(attrs.length+ops.length)*row+34;
  const divider=y+head+attrs.length*row+8;
  return {h,svg:`<g filter="url(#shadow)"><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="8" fill="white" stroke="${C.blue}" stroke-width="2"/><rect x="${x}" y="${y}" width="${w}" height="${head}" rx="8" fill="${C.sky}"/><rect x="${x}" y="${y+head-8}" width="${w}" height="8" fill="${C.sky}"/>${stereo?textLines(x+w/2,y+23,[stereo],{size:12,italic:true,anchor:"middle",fill:C.muted}):""}${textLines(x+w/2,y+(stereo?49:34),[title],{size:17,weight:700,anchor:"middle",fill:C.navy})}${attrs.map((a,i)=>textLines(x+15,y+head+25+i*row,[a],{size:13})).join("")}<line x1="${x}" y1="${divider}" x2="${x+w}" y2="${divider}" stroke="${C.line}"/>${ops.map((o,i)=>textLines(x+15,divider+27+i*row,[o],{size:13,fill:C.navy})).join("")}</g>`};
}

function classDiagram() {
  const a=umlClass(75,195,220,"Application",["- config: Config","- logger: Logger"],["+ run(): None"]);
  const m=umlClass(370,180,280,"InformeMargenModule",["- processor","- services"],["+ run(): None","+ load_catalogs()"]);
  const p=umlClass(735,180,255,"FBL1NProcessor",["- validator"],["+ process(df)","+ normalize_columns()"]);
  const api=umlClass(1080,180,300,"FastAPI Routes",["- dependencies"],["+ get_dashboard()","+ get_history()"],{stereo:"«interface»"});
  const l=umlClass(190,535,250,"ExcelLoader",["- engine"],["+ load_fbl1n(path)","+ load_catalog(path)"]);
  const s=umlClass(565,535,245,"MatrizService",["- classifiers"],["+ build(df)","+ enrich(df)"]);
  const o=umlClass(960,535,330,"OutputArtifactService",["- output_dir"],["+ latest()","+ read_state()"]);
  const body=`${a.svg}${m.svg}${p.svg}${api.svg}${l.svg}${s.svg}${o.svg}
    ${pathLine("M295,255 H370",{marker:"openArrow"})}${pathLine("M650,255 H735",{marker:"openArrow"})}
    ${pathLine("M490,388 V455 H315 V535",{marker:"openArrow"})}${pathLine("M530,388 V470 H687 V535",{marker:"openArrow"})}
    ${pathLine("M1080,300 H1030 V535 H1125",{dash:true,marker:"openArrow"})}${pathLine("M810,650 H960",{marker:"openArrow"})}
    ${label(330,239,"delegación")}${label(692,239,"composición")}${label(1015,405,"«uses»")}
  `;
  return base("Diagrama de Clases", "Responsabilidades principales y dependencias de la solución", body);
}

function participant(x,title,sub="") {
  return `<g><rect x="${x-92}" y="166" width="184" height="64" rx="9" fill="${C.sky}" stroke="${C.blue}" stroke-width="2"/>${textLines(x,194,[title],{size:15,weight:700,anchor:"middle",fill:C.navy})}${sub?textLines(x,216,[sub],{size:11,anchor:"middle",fill:C.muted}):""}<line x1="${x}" y1="230" x2="${x}" y2="790" stroke="${C.line}" stroke-width="1.5" stroke-dasharray="7 7"/></g>`;
}

function message(x1,x2,y,text,{returnMsg=false}={}) {
  return `${pathLine(`M${x1},${y} H${x2}`,{dash:returnMsg,marker:returnMsg?"openArrow":"arrow",width:1.8})}${label((x1+x2)/2,y-8,text,{size:12})}`;
}

function sequenceDiagram() {
  const xs=[130,380,625,875,1130,1390];
  const body=`${participant(xs[0],"Scheduler")}${participant(xs[1],"run_diario.py")}${participant(xs[2],"SAP GUI")}${participant(xs[3],"Orquestador")}${participant(xs[4],"Excel / SharePoint")}${participant(xs[5],"Outlook")}
    <rect x="365" y="282" width="30" height="430" fill="${C.sky}" stroke="${C.blue}"/><rect x="860" y="440" width="30" height="275" fill="${C.sky}" stroke="${C.blue}"/>
    ${message(xs[0],xs[1],275,"iniciar tarea programada")}${message(xs[1],xs[2],380,"extraer FBL1N")}${message(xs[2],xs[1],430,"archivo exportado",{returnMsg:true})}${message(xs[1],xs[3],475,"ejecutar actualización")}${message(xs[3],xs[4],535,"generar y validar artefactos")}${message(xs[4],xs[3],595,"artefactos listos",{returnMsg:true})}${message(xs[3],xs[4],655,"publicar versión actual")}${message(xs[3],xs[5],715,"notificar si corresponde")}${message(xs[3],xs[1],770,"resultado y estado",{returnMsg:true})}
    <rect x="335" y="318" width="585" height="134" fill="none" stroke="${C.orange}" stroke-width="1.7"/><rect x="335" y="318" width="90" height="25" fill="${C.orangePale}" stroke="${C.orange}"/><text x="348" y="336" font-family="Segoe UI, Arial" font-size="12" font-weight="700" fill="${C.orange}">alt</text>${textLines(440,337,["SAP disponible / error controlado"],{size:12,fill:C.muted})}
  `;
  return base("Diagrama de Secuencia", "Flujo diario de extracción, procesamiento, publicación y notificación", body);
}

function component(x,y,w,h,title,lines=[],opts={}) {
  const fill=opts.external?C.orangePale:C.white, stroke=opts.external?C.orange:C.blue, head=opts.external?C.orangePale:C.sky;
  return `<g filter="url(#shadow)"><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="10" fill="${fill}" stroke="${stroke}" stroke-width="2"/><rect x="${x+w-44}" y="${y+13}" width="25" height="13" fill="${head}" stroke="${stroke}"/><rect x="${x+w-51}" y="${y+32}" width="25" height="13" fill="${head}" stroke="${stroke}"/>${textLines(x+w/2,y+47,[title],{size:17,weight:700,anchor:"middle",fill:opts.external?C.orange:C.navy})}${lines.length?textLines(x+w/2,y+78,lines,{size:13,anchor:"middle",lineHeight:19,fill:C.ink}):""}</g>`;
}

function componentDiagram() {
  const body=`
    <rect x="65" y="165" width="1470" height="590" rx="14" fill="${C.pale}" stroke="${C.line}"/><text x="90" y="197" font-family="Segoe UI, Arial" font-size="15" font-weight="700" fill="${C.muted}">ENTORNO DE EJECUCIÓN WINDOWS</text>
    <rect x="95" y="225" width="450" height="465" rx="12" fill="white" stroke="${C.line}"/><text x="120" y="255" font-family="Segoe UI, Arial" font-size="14" font-weight="700" fill="${C.navy}">CAPA DE PRESENTACIÓN</text>
    ${component(145,295,350,125,"Interfaz React",["TypeScript + Vite"]) }
    ${component(145,505,350,125,"API FastAPI",["Endpoints de lectura"]) }
    <rect x="585" y="225" width="510" height="465" rx="12" fill="white" stroke="${C.line}"/><text x="610" y="255" font-family="Segoe UI, Arial" font-size="14" font-weight="700" fill="${C.navy}">CAPA DE APLICACIÓN</text>
    ${component(635,295,410,125,"Orquestador Python",["Validación + reglas + estados"]) }
    ${component(635,505,190,125,"Procesamiento",["pandas","openpyxl"]) }
    ${component(855,505,190,125,"Artefactos",["Excel + JSON"]) }
    <rect x="1135" y="225" width="350" height="465" rx="12" fill="white" stroke="${C.line}"/><text x="1160" y="255" font-family="Segoe UI, Arial" font-size="14" font-weight="700" fill="${C.navy}">SERVICIOS EMPRESARIALES</text>
    ${component(1185,285,250,90,"SAP GUI",["FBL1N"],{external:true})}${component(1185,405,250,90,"Excel / SharePoint",["Publicación"],{external:true})}${component(1185,525,250,90,"Outlook / Power BI",["Notificación y análisis"],{external:true})}
    ${pathLine("M320,420 V505",{marker:"openArrow"})}${pathLine("M495,565 H565 V357 H635",{dash:true,marker:"openArrow"})}${pathLine("M840,420 V505",{marker:"openArrow"})}${pathLine("M825,568 H855",{marker:"openArrow"})}
    ${pathLine("M1045,340 H1185",{dash:true})}${pathLine("M1045,565 H1110 V450 H1185",{dash:true})}${pathLine("M1045,590 H1135 V570 H1185",{dash:true})}
    ${label(560,333,"JSON / HTTP")}${label(1110,323,"GUI Scripting")}${label(1110,478,"COM / sincronización")}
  `;
  return base("Diagrama de Componentes", "Distribución de responsabilidades e integraciones empresariales", body);
}

const diagrams = [
  ["01_casos_de_uso", useCases()],
  ["02_modelo_logico_datos", dataModel()],
  ["03_diagrama_de_clases", classDiagram()],
  ["04_diagrama_de_secuencia", sequenceDiagram()],
  ["05_diagrama_de_componentes", componentDiagram()],
];

for (const [name, svg] of diagrams) {
  const svgPath = path.join(workDir, `${name}.svg`);
  const pngPath = path.join(outDir, `${name}.png`);
  fs.writeFileSync(svgPath, svg, "utf8");
  await sharp(Buffer.from(svg)).resize(3200, 1800, { fit: "fill" }).png({ compressionLevel: 9 }).toFile(pngPath);
  process.stdout.write(`${pngPath}\n`);
}
