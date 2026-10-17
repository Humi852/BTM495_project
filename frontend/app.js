const overallStatus = document.querySelector("#overall-status");
const databaseName = document.querySelector("#database-name");
const errorMessage = document.querySelector("#error-message");
const tableResults = document.querySelector("#table-results");
const refreshButton = document.querySelector("#refresh-button");

function setStatus(label, state) {
  overallStatus.textContent = label;
  overallStatus.className = `status status-${state}`;
}

function renderTables(tables) {
  tableResults.replaceChildren();

  if (tables.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 3;
    cell.className = "muted";
    cell.textContent = "Connected; no application tables were found.";
    row.append(cell);
    tableResults.append(row);
    return;
  }

  for (const table of tables) {
    const row = document.createElement("tr");
    const nameCell = document.createElement("td");
    const countCell = document.createElement("td");
    const resultCell = document.createElement("td");

    nameCell.textContent = table.name;
    countCell.textContent = String(table.rows);
    resultCell.textContent = "Readable";
    resultCell.className = "row-ok";
    row.append(nameCell, countCell, resultCell);
    tableResults.append(row);
  }
}

async function runTest() {
  refreshButton.disabled = true;
  errorMessage.hidden = true;
  databaseName.textContent = "Checking local SQLite database…";
  tableResults.replaceChildren();
  setStatus("Checking…", "pending");

  try {
    const response = await fetch("/api/status", { cache: "no-store" });
    const result = await response.json();

    if (!response.ok || result.status !== "ok") {
      throw new Error(result.message || `API returned HTTP ${response.status}`);
    }

    databaseName.textContent = `Connected to ${result.database}`;
    renderTables(result.tables);
    setStatus("All checks passed", "ok");
  } catch (error) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 3;
    cell.className = "muted";
    cell.textContent = "No database table results available.";
    row.append(cell);
    tableResults.append(row);

    const message = error instanceof Error ? error.message : String(error);
    databaseName.textContent = "Database check failed";
    errorMessage.textContent = message;
    errorMessage.hidden = false;
    setStatus("Check failed", "error");
  } finally {
    refreshButton.disabled = false;
  }
}

refreshButton.addEventListener("click", runTest);
runTest();
