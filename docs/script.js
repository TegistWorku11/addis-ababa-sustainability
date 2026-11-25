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

// Assign colors based on sustainability risk
function getRiskColor(score) {
    if (score >= 0.8) return "#b91c1c";
    if (score >= 0.6) return "#ef4444";
    if (score >= 0.4) return "#f59e0b";
    if (score >= 0.2) return "#84cc16";
    return "#15803d";
}

// Load woreda boundary data
fetch("assets/data/addis_ababa_woreda_public.geojson")
    .then(response => {
        if (!response.ok) {
            throw new Error("Unable to load GeoJSON");
        }
        return response.json();
    })
    .then(data => {

        // Inspect the data in the browser console
        console.log(data);

        // Create the geographic overlay
        const woredaLayer = L.geoJSON(data, {
            style: function(feature) {
                return {
                color: "#ffffff",
                weight: 1,
                fillColor: getRiskColor(
                    feature.properties.risk_score
                ),
                fillOpacity: 0.4
            }
        }).addTo(riskMap);

        // Adjust the map to fit all woreda boundaries
        riskMap.fitBounds(woredaLayer.getBounds());

    })
    .catch(error => {
        console.error("Map data error:", error);
    });
