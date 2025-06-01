let cart = [];

function addToCart(item) {
  cart.push(item);
  updateCart();
}

function updateCart() {
  const cartEl = document.getElementById("cart");
  cartEl.innerHTML = "";
  cart.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    cartEl.appendChild(li);
  });
}

function simulateAbandonCart() {
  const name = document.getElementById("name").value;
  const phone = document.getElementById("phone").value;

  if (!name || !phone || cart.length === 0) {
    alert("Fill name, phone, and add at least one item.");
    return;
  }

  const data = {
    user: {
      name: name,
      phone: phone
    },
    cart: cart
  };

  fetch("/abandon_cart", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(data)
  })
    .then((res) => res.json())
    .then((data) => {
      alert(data.message);
    })
    .catch((err) => {
      console.error(err);
      alert("Error sending cart data.");
    });
}
