// JavaScript will make the site interactive.
console.log('Addis Ababa case study website loaded.');
// Initialize the Addis Ababa map
const riskMap = L.map("risk-map").setView(
    [9.03, 38.74],
    11
);

// Add the OpenStreetMap base layer
L.tileLayer(
    "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    {
        maxZoom: 19,
        attribution: "&copy; OpenStreetMap contributors"
    }
).addTo(riskMap);
