"""Static HTML template for the offline graph visualization."""

# Kept as one literal so the standalone HTML asset stays editable as a whole.
HTML_TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Atelier v1 - Graphe</title>
<style>
body{font-family:Arial;margin:0;background:#f8fafc}
header{padding:8px 12px;background:#1e293b;color:#fff}
svg{width:100vw;height:calc(100vh - 42px)}
</style></head>
<body><header>Atelier v1 - Graphe des relations</header><svg id="canvas"></svg>
<script>
const data = __GRAPH_DATA__;
const colors = {Universe:"#0ea5e9",Source:"#22c55e",
  Document:"#f59e0b",Candidate:"#a855f7"};
const canvas = document.getElementById("canvas");
const nodes = data.nodes.map((node, i) => ({
  ...node, x: 90 + (i * 71) % 900, y: 80 + (i * 97) % 520}));
function findNode(id) {
  return nodes.find(node => node.id === id) || null;
}
function draw() {
  canvas.innerHTML = "";
  for (const edge of data.edges) {
    const from = findNode(edge.source), to = findNode(edge.target);
    if (!from || !to) continue;
    const line = document.createElementNS(
      "http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", from.x);
    line.setAttribute("y1", from.y);
    line.setAttribute("x2", to.x);
    line.setAttribute("y2", to.y);
    line.setAttribute("stroke", "#94a3b8");
    canvas.appendChild(line);
  }
  for (const node of nodes) {
    const circle = document.createElementNS(
      "http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("cx", node.x);
    circle.setAttribute("cy", node.y);
    circle.setAttribute("r", 14);
    circle.setAttribute("fill", colors[node.kind] || "#64748b");
    canvas.appendChild(circle);
    const text = document.createElementNS(
      "http://www.w3.org/2000/svg", "text");
    text.setAttribute("x", node.x + 18);
    text.setAttribute("y", node.y + 4);
    text.setAttribute("font-size", "12");
    text.textContent = node.kind + ": " + node.label;
    canvas.appendChild(text);
  }
}
draw();
window.addEventListener("resize", draw);
</script></body></html>
"""
