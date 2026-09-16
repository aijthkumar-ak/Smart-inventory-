// ======================================
// SMART INVENTORY - SCRIPT
// ======================================

let products = JSON.parse(
    localStorage.getItem("smartInventoryProducts")
) || [];

const modal = document.getElementById("productModal");
const form = document.getElementById("productForm");


// ======================================
// OPEN PRODUCT FORM
// ======================================

function openProductForm() {
    modal.style.display = "flex";

    document.getElementById("productName").focus();
}


// ======================================
// CLOSE PRODUCT FORM
// ======================================

function closeProductForm() {
    modal.style.display = "none";

    form.reset();
}


// ======================================
// ADD PRODUCT
// ======================================

form.addEventListener("submit", function (event) {

    event.preventDefault();

    const name =
        document.getElementById("productName").value.trim();

    const category =
        document.getElementById("productCategory").value;

    const stock =
        Number(document.getElementById("productStock").value);

    const price =
        Number(document.getElementById("productPrice").value);


    if (!name || !category || stock < 0 || price < 0) {
        alert("Please enter valid product details.");
        return;
    }


    const product = {

        id: Date.now(),

        name: name,

        category: category,

        stock: stock,

        price: price

    };


    products.push(product);

    saveProducts();

    renderProducts();

    updateDashboard();

    closeProductForm();

});


// ======================================
// SAVE PRODUCTS
// ======================================

function saveProducts() {

    localStorage.setItem(
        "smartInventoryProducts",
        JSON.stringify(products)
    );

}


// ======================================
// DISPLAY PRODUCTS
// ======================================

function renderProducts(list = products) {

    const table =
        document.getElementById("productTable");


    if (list.length === 0) {

        table.innerHTML = `
            <tr>
                <td colspan="6" class="empty">
                    No products added yet.
                </td>
            </tr>
        `;

        return;
    }


    table.innerHTML = "";


    list.forEach(product => {

        let status = "";
        let statusClass = "";


        if (product.stock === 0) {

            status = "Out of Stock";
            statusClass = "status-out";

        } else if (product.stock <= 10) {

            status = "Low Stock";
            statusClass = "status-low";

        } else {

            status = "In Stock";
            statusClass = "status-good";

        }


        const row = document.createElement("tr");


        row.innerHTML = `

            <td>
                <strong>${product.name}</strong>
            </td>

            <td>
                ${product.category}
            </td>

            <td>
                ${product.stock}
            </td>

            <td>
                ₹${product.price.toLocaleString("en-IN")}
            </td>

            <td>
                <span class="status ${statusClass}">
                    ${status}
                </span>
            </td>

            <td>

                <button
                    class="action-btn edit-btn"
                    onclick="editProduct(${product.id})">
                    Edit
                </button>

                <button
                    class="action-btn delete-btn"
                    onclick="deleteProduct(${product.id})">
                    Delete
                </button>

            </td>
        `;


        table.appendChild(row);

    });

}


// ======================================
// UPDATE DASHBOARD
// ======================================

function updateDashboard() {

    // Total Products

    document.getElementById("totalProducts").textContent =
        products.length;


    // Low Stock

    const lowStock =
        products.filter(
            product => product.stock > 0 && product.stock <= 10
        ).length;

    document.getElementById("lowStock").textContent =
        lowStock;


    // Inventory Value

    const totalValue =
        products.reduce(
            (total, product) =>
                total + (product.stock * product.price),
            0
        );


    document.getElementById("inventoryValue").textContent =
        "₹" + totalValue.toLocaleString("en-IN");


    // Suppliers

    document.getElementById("supplierCount").textContent =
        new Set(products.map(product => product.category)).size;

}


// ======================================
// SEARCH
// ======================================

function searchProducts() {

    const search =
        document.getElementById("searchInput")
            .value
            .toLowerCase()
            .trim();


    const filtered =
        products.filter(product =>

            product.name
                .toLowerCase()
                .includes(search)

            ||

            product.category
                .toLowerCase()
                .includes(search)

        );


    renderProducts(filtered);

}


// ======================================
// DELETE PRODUCT
// ======================================

function deleteProduct(id) {

    const confirmDelete =
        confirm("Delete this product?");


    if (!confirmDelete) {
        return;
    }


    products =
        products.filter(product => product.id !== id);


    saveProducts();

    renderProducts();

    updateDashboard();

}


// ======================================
// EDIT PRODUCT
// ======================================

function editProduct(id) {

    const product =
        products.find(product => product.id === id);


    if (!product) {
        return;
    }


    const newName =
        prompt("Product Name:", product.name);


    if (newName === null) {
        return;
    }


    const newStock =
        prompt("Stock Quantity:", product.stock);


    if (newStock === null) {
        return;
    }


    const newPrice =
        prompt("Price:", product.price);


    if (newPrice === null) {
        return;
    }


    product.name =
        newName.trim();


    product.stock =
        Number(newStock);


    product.price =
        Number(newPrice);


    saveProducts();

    renderProducts();

    updateDashboard();

}


// ======================================
// CLOSE MODAL WHEN CLICK OUTSIDE
// ======================================

window.addEventListener("click", function (event) {

    if (event.target === modal) {

        closeProductForm();

    }

});


// ======================================
// INITIAL LOAD
// ======================================

renderProducts();

updateDashboard();