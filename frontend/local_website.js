const overallStatus = document.querySelector("#overall-status");
const databaseName = document.querySelector("#database-name");
const errorMessage = document.querySelector("#error-message");
const tableResults = document.querySelector("#table-results");
const orderResults = document.querySelector("#order-results");
const paymentHistory = document.querySelector("#payment-history");
const orderMessage = document.querySelector("#order-message");
const refreshButton = document.querySelector("#refresh-button");
const makePaymentButton = document.querySelector("#make-payment-button");
const paymentDialog = document.querySelector("#payment-dialog");
const paymentForm = document.querySelector("#payment-form");
const orderSelect = document.querySelector("#order-id");
const paymentError = document.querySelector("#payment-error");
const confirmPaymentButton = document.querySelector("#confirm-payment-button");
const loginForm = document.querySelector("#login-form");
const loginButton = document.querySelector("#login-button");
const loginMessage = document.querySelector("#login-message");
const loginError = document.querySelector("#login-error");

let currentOrders = [];

function setStatus(label, state) {
  overallStatus.textContent = label;
  overallStatus.className = `status status-${state}`;
}

function appendMessageRow(target, columnCount, message) {
  const row = document.createElement("tr");
  const cell = document.createElement("td");
  cell.colSpan = columnCount;
  cell.className = "muted";
  cell.textContent = message;
  row.append(cell);
  target.replaceChildren(row);
}

function renderTables(tables) {
  tableResults.replaceChildren();
  if (tables.length === 0) {
    appendMessageRow(tableResults, 2, "No application tables were found.");
    return;
  }

  for (const table of tables) {
    const row = document.createElement("tr");
    const nameCell = document.createElement("td");
    const countCell = document.createElement("td");
    nameCell.textContent = table.name;
    countCell.textContent = String(table.rows);
    row.append(nameCell, countCell);
    tableResults.append(row);
  }
}

function formatAmount(amount) {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "USD",
  }).format(amount);
}

function renderOrders(orders) {
  currentOrders = orders;
  orderResults.replaceChildren();
  orderSelect.replaceChildren();

  const unpaidOrders = orders.filter((order) => !order.paid);
  if (unpaidOrders.length === 0) {
    if (orders.length === 0) {
      appendMessageRow(orderResults, 4, "No orders are available.");
      orderMessage.textContent = "A sample order will be created when you start a payment.";
    } else {
      orderMessage.textContent = "All current orders are paid. A new sample order will be created for testing.";
    }
    makePaymentButton.disabled = false;
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No unpaid orders";
    orderSelect.append(option);
  } else {
    orderMessage.textContent = `${unpaidOrders.length} unpaid order(s) available.`;
    makePaymentButton.disabled = false;
    for (const order of unpaidOrders) {
      const option = document.createElement("option");
      option.value = String(order.order_id);
      option.textContent = `#${order.order_id} — ${formatAmount(order.total_amount)}`;
      orderSelect.append(option);
    }
  }

  for (const order of orders) {
    const row = document.createElement("tr");
    const values = [
      `#${order.order_id}`,
      order.order_date || "—",
      formatAmount(order.total_amount),
      order.paid ? "Paid" : "Unpaid",
    ];
    for (const value of values) {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.append(cell);
    }
    row.lastElementChild.className = order.paid ? "row-ok" : "row-pending";
    orderResults.append(row);
  }
}

function renderPayments(payments) {
  paymentHistory.replaceChildren();
  if (payments.length === 0) {
    appendMessageRow(paymentHistory, 6, "No payment history yet.");
    return;
  }

  for (const payment of payments) {
    const row = document.createElement("tr");
    const values = [
      `#${payment.payment_id}`,
      `#${payment.order_id}`,
      payment.payment_date,
      formatAmount(payment.amount),
      payment.payment_method,
      payment.paid_status ? "Approved" : "Declined",
    ];
    for (const value of values) {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.append(cell);
    }
    row.lastElementChild.className = payment.paid_status ? "row-ok" : "row-pending";
    paymentHistory.append(row);
  }
}

async function loadDashboard() {
  refreshButton.disabled = true;
  errorMessage.hidden = true;
  databaseName.textContent = "Loading SQLite data…";
  setStatus("Loading…", "pending");

  try {
    const response = await fetch("/api/dashboard", { cache: "no-store" });
    const result = await response.json();
    if (!response.ok || result.status !== "ok") {
      throw new Error(result.message || `API returned HTTP ${response.status}`);
    }

    databaseName.textContent = `Connected to ${result.database}`;
    renderTables(result.tables);
    renderOrders(result.orders);
    renderPayments(result.payments);
    setStatus("Database connected", "ok");
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    databaseName.textContent = "Could not load database data";
    errorMessage.textContent = message;
    errorMessage.hidden = false;
    setStatus("Connection failed", "error");
    appendMessageRow(tableResults, 2, "Database structure unavailable.");
    appendMessageRow(orderResults, 4, "Orders unavailable.");
    appendMessageRow(paymentHistory, 6, "Payment history unavailable.");
    makePaymentButton.disabled = true;
  } finally {
    refreshButton.disabled = false;
  }
}

async function submitLogin(event) {
  event.preventDefault();
  loginError.hidden = true;
  loginMessage.textContent = "";
  loginButton.disabled = true;

  try {
    const formData = new FormData(loginForm);
    const response = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: formData.get("email"),
        password: formData.get("password"),
      }),
    });
    const result = await response.json();
    if (!response.ok || result.status !== "ok") {
      throw new Error(result.message || `Login failed with HTTP ${response.status}`);
    }

    const role = result.user.is_admin ? "Admin" : "Customer";
    loginMessage.textContent = `Login check passed for ${result.user.name} (${role}).`;
    loginForm.reset();
  } catch (error) {
    loginError.textContent = error instanceof Error ? error.message : String(error);
    loginError.hidden = false;
  } finally {
    loginButton.disabled = false;
  }
}

async function startPayment() {
  if (currentOrders.some((order) => !order.paid)) {
    openPaymentDialog();
    return;
  }

  makePaymentButton.disabled = true;
  errorMessage.hidden = true;
  try {
    const response = await fetch("/api/sample-orders", { method: "POST" });
    const result = await response.json();
    if (!response.ok || result.status !== "ok") {
      throw new Error(result.message || `Could not create a sample order (HTTP ${response.status})`);
    }

    await loadDashboard();
    if (!currentOrders.some((order) => order.order_id === result.order.order_id)) {
      throw new Error("The sample order was created, but the order list could not be refreshed.");
    }
    openPaymentDialog();
  } catch (error) {
    errorMessage.textContent = error instanceof Error ? error.message : String(error);
    errorMessage.hidden = false;
  } finally {
    makePaymentButton.disabled = false;
  }
}

function openPaymentDialog() {
  paymentError.hidden = true;
  paymentForm.reset();
  if (typeof paymentDialog.showModal === "function") {
    paymentDialog.showModal();
  } else {
    paymentDialog.setAttribute("open", "");
  }
  orderSelect.focus();
}

function closePaymentDialog() {
  if (typeof paymentDialog.close === "function" && paymentDialog.open) {
    paymentDialog.close();
  } else {
    paymentDialog.removeAttribute("open");
  }
  paymentForm.reset();
}

async function submitPayment(event) {
  event.preventDefault();
  paymentError.hidden = true;

  const selectedOrder = currentOrders.find(
    (order) => String(order.order_id) === orderSelect.value,
  );
  if (!selectedOrder || selectedOrder.paid) {
    paymentError.textContent = "Select an unpaid order.";
    paymentError.hidden = false;
    return;
  }

  const confirmed = window.confirm(
    `Confirm mock payment of ${formatAmount(selectedOrder.total_amount)} for order #${selectedOrder.order_id}?`,
  );
  if (!confirmed) {
    return;
  }

  confirmPaymentButton.disabled = true;
  try {
    const formData = new FormData(paymentForm);
    const response = await fetch("/api/payments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        order_id: Number(formData.get("order_id")),
        card_number: formData.get("card_number"),
        expiration_date: formData.get("expiration_date"),
        cvv: formData.get("cvv"),
      }),
    });
    const result = await response.json();
    if (!response.ok || result.status !== "ok") {
      throw new Error(result.message || `Payment failed with HTTP ${response.status}`);
    }

    if (!result.payment.paid_status) {
      setStatus("Payment declined", "error");
      paymentError.textContent =
        "Payment declined. The order remains unpaid. This demo approves only " +
        "card number 4242424242424242 with a valid MM/YY expiration and a " +
        "3-digit security code. Check your details and try again.";
      paymentError.hidden = false;
      document.querySelector("#card-number").focus();
      return;
    }

    closePaymentDialog();
    await loadDashboard();
    setStatus("Payment Successful", "ok");
  } catch (error) {
    paymentError.textContent = error instanceof Error ? error.message : String(error);
    paymentError.hidden = false;
  } finally {
    confirmPaymentButton.disabled = false;
  }
}

refreshButton.addEventListener("click", loadDashboard);
makePaymentButton.addEventListener("click", startPayment);
document.querySelector("#close-dialog-button").addEventListener("click", closePaymentDialog);
document.querySelector("#cancel-payment-button").addEventListener("click", closePaymentDialog);
paymentForm.addEventListener("submit", submitPayment);
loginForm.addEventListener("submit", submitLogin);
loadDashboard();
