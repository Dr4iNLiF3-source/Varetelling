from flask import Flask, request, jsonify
import sqlite3
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@app.route('/get_inventory', methods=['GET'])
def get_inventory():
    logging.info("Received request to get inventory")
    
    with sqlite3.connect("inventory.db") as conn:
        cur = conn.cursor()
        cur.execute("SELECT products.id, products.name, products.barcode, quantities.quantity FROM products INNER JOIN quantities ON products.id = quantities.product_id")
        inventory = cur.fetchall()
    
    logging.info("Inventory retrieved successfully")
    print(inventory)
    return jsonify(inventory)

@app.route('/check_barcode', methods=['POST'])
def check_barcode():
    data = request.get_json()
    barcode = data.get("barcode")
    logging.info(f"Received request to check barcode: {barcode}")
    
    with sqlite3.connect("inventory.db") as conn:
        cur = conn.cursor()
        
        # Check if barcode exists
        cur.execute("SELECT id, name FROM products WHERE barcode=?", (barcode,))
        product = cur.fetchone()
        
        if product:
            logging.info(f"Barcode {barcode} exists with product name: {product[1]}")
            return jsonify({"exists": True, "id": product[0], "name": product[1]})
        else:
            logging.info(f"Barcode {barcode} does not exist")
            return jsonify({"exists": False})

@app.route('/add_product', methods=['POST'])
def add_product():
    data = request.get_json()
    barcode = data.get("barcode")
    name = data.get("name")
    logging.info(f"Received request to add product with barcode: {barcode}, name: {name}")
    
    with sqlite3.connect("inventory.db") as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO products (barcode, name) VALUES (?, ?)", (barcode, name))
        conn.commit()
        cur.execute("SELECT id FROM products WHERE barcode=?", (barcode,))
        product_id = cur.fetchone()[0]
        cur.execute("INSERT INTO quantities (product_id, quantity) VALUES (?, ?)", (product_id, 1))
        conn.commit()
        
    
    logging.info(f"Product with barcode: {barcode}, name: {name} added successfully")
    return jsonify({"status": "added"})

@app.route('/add_quantity', methods=['POST'])
def add_quantity():
    data = request.get_json()
    product_id = data.get("product_id")
    quantity = data.get("quantity")
    logging.info(f"Received request to add quantity: {quantity} for product_id: {product_id}")
    
    with sqlite3.connect("inventory.db") as conn:
        cur = conn.cursor()
        # add quantity to quantities table where product_id exists
        cur.execute("UPDATE quantities SET quantity = quantity + ? WHERE product_id=?", (quantity, product_id))
        conn.commit()
    
    logging.info(f"Quantity: {quantity} added for product_id: {product_id}")
    return jsonify({"status": "quantity added"})

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)