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
            style: {
                color: "#2563eb",
                weight: 1,
                fillColor: "#60a5fa",
                fillOpacity: 0.4
            }
        }).addTo(riskMap);

        // Adjust the map to fit all woreda boundaries
        riskMap.fitBounds(woredaLayer.getBounds());

    })
    .catch(error => {
        console.error("Map data error:", error);
    });
