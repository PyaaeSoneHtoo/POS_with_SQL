import sys
import sqlite3
import os
import datetime
import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QTableWidgetItem, QFileDialog, QCompleter,
                            QHeaderView, QMessageBox, QStackedWidget, QDialog, QFormLayout, QComboBox, QLineEdit, QDialogButtonBox)
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6 import uic

DB_FILE = "pos.db"

# ==========================================
# DATABASE LOGIC
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        staff_name TEXT DEFAULT 'Unknown',
        joining_date TEXT DEFAULT '01.01.2025',
        mobile_number TEXT DEFAULT '0000000000',
        number_of_login INTEGER DEFAULT 0,
        transitions INTEGER DEFAULT 0,
        total_amount REAL DEFAULT 0.0
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_number TEXT UNIQUE,
        barcode TEXT,
        description TEXT,
        product_name TEXT NOT NULL,
        purchase_price REAL,
        sale_price REAL NOT NULL,
        stock INTEGER DEFAULT 100
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS purchase_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        po_number TEXT UNIQUE NOT NULL,
        created_by TEXT NOT NULL,
        date TEXT NOT NULL,
        vendor_id TEXT,
        vendor_name TEXT,
        total_qty INTEGER,
        total_amount REAL,
        invoice_pdf TEXT
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS purchase_order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        po_id INTEGER,
        item_number TEXT,
        barcode TEXT,
        product_name TEXT,
        cost_price REAL,
        qty INTEGER,
        total REAL,
        FOREIGN KEY (po_id) REFERENCES purchase_orders (id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        total_amount REAL NOT NULL,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        price_at_time REAL NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders (id),
        FOREIGN KEY (product_id) REFERENCES master_products (id)
    )
    ''')
    
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO users (username, password, role) VALUES ('admin', 'admin', 'admin')")
        cursor.execute("INSERT INTO users (username, password, role) VALUES ('user', 'user', 'user')")
        
    conn.commit()
    conn.close()

def verify_login(username, password):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, role FROM users WHERE username=? AND password=?", (username, password))
    result = cursor.fetchone()
    
    if result:
        # Increment number_of_login
        cursor.execute("UPDATE users SET number_of_login = number_of_login + 1 WHERE id=?", (result[0],))
        conn.commit()
        conn.close()
        return result[1]
        
    conn.close()
    return None

def get_all_products():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT item_number, product_name, sale_price, stock FROM products") 
    products = cursor.fetchall()
    conn.close()
    return products

# Initialize DB on script start
init_db()


# ==========================================
# UI LOGIC
# ==========================================
class LoginWindow(QWidget):
    def __init__(self, stacked_widget):
        super().__init__()
        self.stacked_widget = stacked_widget
        uic.loadUi("ui_files/login.ui", self)
        self.loginBtn.clicked.connect(self.handle_login)
        # Connect the new Manager button
        if hasattr(self, 'pushButton'):
            self.pushButton.clicked.connect(self.open_manager_panel)
        
    def handle_login(self):
        # Default Login Button -> Goes to POS Cashier Panel
        username = self.usernameInput.text()
        password = self.passwordInput.text()
        
        role = verify_login(username, password)
        
        if role in ["0", "1", "2"]:
            self.window().current_role = role
            self.window().current_username = username
            self.stacked_widget.setCurrentIndex(1)  # Go to POS Cashier Panel
            self.stacked_widget.widget(1).load_products()
            self.usernameInput.clear()
            self.passwordInput.clear()
        else:
            QMessageBox.warning(self, "Login Failed", "Invalid username or password.")

    def open_manager_panel(self):
        # Manager Button -> Goes to Admin Panel
        username = self.usernameInput.text()
        password = self.passwordInput.text()
        
        role = verify_login(username, password)
        
        if role in ["1", "2"]:
            self.window().current_role = role
            self.window().current_username = username
            self.stacked_widget.setCurrentIndex(2)  # Go to Admin Panel
            self.usernameInput.clear()
            self.passwordInput.clear()
        elif role == "0":
            QMessageBox.warning(self, "Permission Denied", "You do not have permission to access the Manager panel.")
        else:
            QMessageBox.warning(self, "Login Failed", "Invalid username or password.")


class POSWindow(QWidget):
    def __init__(self, stacked_widget):
        super().__init__()
        self.stacked_widget = stacked_widget
        self.cart = []
        self.total = 0.0
        
        uic.loadUi("ui_files/pos.ui", self)
        
        # Setup Cart Table
        self.cartTable.setColumnCount(3)
        self.cartTable.setHorizontalHeaderLabels(["Name", "Qty", "Price"])
        self.cartTable.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        # Connect buttons
        self.logoutBtn.clicked.connect(self.logout)
        
        self.checkoutBtn.clicked.connect(self.checkout)

    def logout(self):
        self.cart = []
        self.update_cart_ui()
        self.stacked_widget.setCurrentIndex(0)

    def load_products(self):
        self.products = get_all_products()
        # products contains: (item_number, product_name, sale_price, stock)
        
        self.search_map = {}
        for p in self.products:
            # We map both item_number and product_name to the product data for easy lookup
            self.search_map[str(p[0]).lower()] = p
            self.search_map[str(p[1]).lower()] = p
            # We can also map barcodes if we update get_all_products later

        # Connect the search box signal so when they hit 'Enter', it adds to cart
        if hasattr(self, 'searchBox'):
            # Disconnect first to avoid multiple signals if called twice
            try: self.searchBox.returnPressed.disconnect()
            except: pass
            self.searchBox.returnPressed.connect(self.search_and_add)
            
    def search_and_add(self):
        query = self.searchBox.text().strip().lower()
        if not query: return
        
        # Check if the query matches an item number or name in our cached dictionary
        if query in self.search_map:
            prod = self.search_map[query]
            pid = str(prod[0])
            name = str(prod[1])
            price = float(prod[2])
            stock = int(prod[3])
            
            if stock <= 0:
                QMessageBox.warning(self, "Out of Stock", f"{name} is currently out of stock!")
                self.searchBox.clear()
                return
                
            # Add to cart
            found = False
            for item in self.cart:
                if item['id'] == pid:
                    item['qty'] += 1
                    found = True
                    break
                    
            if not found:
                self.cart.append({'id': pid, 'name': name, 'price': price, 'qty': 1})
                
            self.update_cart_ui()
            self.searchBox.clear()
        else:
            # Fallback to database search to include Barcodes
            import sqlite3
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT item_number, product_name, sale_price, stock FROM products WHERE barcode=? OR item_number=? OR LOWER(product_name)=? LIMIT 1", (query, query, query))
            res = cursor.fetchone()
            conn.close()
            
            if res:
                pid = str(res[0])
                name = str(res[1])
                price = float(res[2])
                stock = int(res[3])
                
                if stock <= 0:
                    QMessageBox.warning(self, "Out of Stock", f"{name} is currently out of stock!")
                    self.searchBox.clear()
                    return
                    
                found = False
                for item in self.cart:
                    if item['id'] == pid:
                        item['qty'] += 1
                        found = True
                        break
                        
                if not found:
                    self.cart.append({'id': pid, 'name': name, 'price': price, 'qty': 1})
                    
                self.update_cart_ui()
                self.searchBox.clear()
            else:
                QMessageBox.warning(self, "Not Found", f"No product found matching: '{query}'")
                self.searchBox.clear()
                
    def add_to_cart(self):
        # We replaced the Add button with the search_and_add scanner logic
        pass
        
    def update_cart_ui(self):
        self.cartTable.setRowCount(len(self.cart))
        self.total = 0.0
        
        for row, item in enumerate(self.cart):
            self.cartTable.setItem(row, 0, QTableWidgetItem(item['name']))
            self.cartTable.setItem(row, 1, QTableWidgetItem(str(item['qty'])))
            item_total = item['price'] * item['qty']
            self.cartTable.setItem(row, 2, QTableWidgetItem(f"{item_total:.2f} Dhs"))
            self.total += item_total
            
        self.totalLabel.setText(f"Total: {self.total:.2f} Dhs")

    def checkout(self):
        if not self.cart:
            QMessageBox.warning(self, "Error", "Cart is empty!")
            return
            
        QMessageBox.information(self, "Success", f"Payment of {self.total:.2f} Dhs received successfully!")
        self.cart = []
        self.update_cart_ui()


class AdminWindow(QWidget):
    def __init__(self, stacked_widget):
        super().__init__()
        self.stacked_widget = stacked_widget
        uic.loadUi("ui_files/admin.ui", self)
        
        # We are using a QListWidget now (since you edited it in Qt Designer)
        if hasattr(self, 'menuList') and hasattr(self, 'adminStackedWidget'):
            # Connect the signal for QListWidget
            self.menuList.currentRowChanged.connect(self.switch_admin_page)
            
            # Default to first selection
            self.menuList.setCurrentRow(0)
            
        # Apply clean light gray alternating colors to all admin tables
        if hasattr(self, 'userTable'):
            self.userTable.setStyleSheet("QTableWidget { alternate-background-color: #f2f2f2; background-color: #ffffff; }")
        if hasattr(self, 'poTable'):
            self.poTable.setStyleSheet("QTableWidget { alternate-background-color: #f2f2f2; background-color: #ffffff; }")
        if hasattr(self, 'itemTable'):
            self.itemTable.setStyleSheet("QTableWidget { alternate-background-color: #f2f2f2; background-color: #ffffff; }")
            
        if hasattr(self, 'logoutBtn'):
            self.logoutBtn.clicked.connect(self.logout)
            
        # Hook up Manage User buttons if they exist
        if hasattr(self, 'addUserBtn'):
            self.addUserBtn.clicked.connect(self.add_user_prompt)
        if hasattr(self, 'editUserBtn'):
            self.editUserBtn.clicked.connect(self.edit_user_prompt)
        if hasattr(self, 'deleteUserBtn'):
            self.deleteUserBtn.clicked.connect(self.delete_user_prompt)
        
        # Load users into table on startup
        self.load_users()
        
        # Load POs into table on startup
        if hasattr(self, 'poTable'):
            self.poTable.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            self.load_purchase_orders()
            
        # Hook up PO buttons
        if hasattr(self, 'newPOBtn'):
            self.newPOBtn.clicked.connect(self.new_po_prompt)
        if hasattr(self, 'editPOBtn'):
            self.editPOBtn.clicked.connect(self.edit_po_prompt)
        if hasattr(self, 'savePOBtn'):
            self.savePOBtn.clicked.connect(self.save_po_prompt)
        if hasattr(self, 'deletePOBtn'):
            self.deletePOBtn.clicked.connect(self.delete_po_prompt)
            
        # Hook up Item Menu
        if hasattr(self, 'itemTable'):
            self.itemTable.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            self.load_items()
            
        if hasattr(self, 'newItemBtn'):
            self.newItemBtn.clicked.connect(self.new_item_prompt)
        if hasattr(self, 'editItemBtn'):
            self.editItemBtn.clicked.connect(self.edit_item_prompt)
        if hasattr(self, 'deleteItemBtn'):
            self.deleteItemBtn.clicked.connect(self.delete_item_prompt)

        # Hook up Vendor Menu
        if hasattr(self, 'vendorTable'):
            self.vendorTable.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            self.vendorTable.setStyleSheet("QTableWidget { alternate-background-color: #f2f2f2; background-color: #ffffff; }")
            self.load_vendors()
            
        if hasattr(self, 'newVendorBtn'):
            self.newVendorBtn.clicked.connect(self.new_vendor_prompt)
        if hasattr(self, 'editVendorBtn'):
            self.editVendorBtn.clicked.connect(self.edit_vendor_prompt)
        if hasattr(self, 'deleteVendorBtn'):
            self.deleteVendorBtn.clicked.connect(self.delete_vendor_prompt)
            
    def load_users(self):
        if not hasattr(self, 'userTable'): return
        
        import sqlite3
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN staff_name TEXT DEFAULT 'Unknown'")
            cursor.execute("ALTER TABLE users ADD COLUMN joining_date TEXT DEFAULT '01.01.2025'")
            cursor.execute("ALTER TABLE users ADD COLUMN mobile_number TEXT DEFAULT '0000000000'")
            cursor.execute("ALTER TABLE users ADD COLUMN number_of_login INTEGER DEFAULT 0")
            cursor.execute("ALTER TABLE users ADD COLUMN transitions INTEGER DEFAULT 0")
            cursor.execute("ALTER TABLE users ADD COLUMN total_amount REAL DEFAULT 0.0")
        except sqlite3.OperationalError:
            pass
            
        cursor.execute("SELECT username, role, staff_name, joining_date, mobile_number, number_of_login, transitions, total_amount FROM users")
        users = cursor.fetchall()
        conn.close()
        
        self.userTable.setRowCount(len(users))
        for row, u in enumerate(users):
            self.userTable.setItem(row, 0, QTableWidgetItem(str(u[0])))
            self.userTable.setItem(row, 1, QTableWidgetItem(str(u[1])))
            self.userTable.setItem(row, 2, QTableWidgetItem(str(u[2])))
            self.userTable.setItem(row, 3, QTableWidgetItem(str(u[3])))
            self.userTable.setItem(row, 4, QTableWidgetItem(str(u[4])))
            self.userTable.setItem(row, 5, QTableWidgetItem(str(u[5])))
            self.userTable.setItem(row, 6, QTableWidgetItem(str(u[6])))
            self.userTable.setItem(row, 7, QTableWidgetItem(f"{u[7]:.2f} Dhs"))
            
        self.userTable.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    def add_user_prompt(self):
        current_role = getattr(self.window(), 'current_role', '1')
        dialog = AddUserDialog(current_role, self)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if not data['username'] or not data['password']:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Error", "Username and Password are required!")
                return
            
            import datetime
            today_str = datetime.datetime.now().strftime('%d.%m.%Y')
            
            import sqlite3
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO users (username, password, role, staff_name, mobile_number, joining_date)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (data['username'], data['password'], data['role'], data['staff_name'], data['mobile_number'], today_str))
                conn.commit()
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(self, "Success", "User added successfully!")
                self.load_users()
            except sqlite3.IntegrityError:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Error", "Username already exists!")
            finally:
                conn.close()

    def edit_user_prompt(self):
        selected = self.userTable.selectionModel().selectedRows()
        if not selected:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Warning", "Please select a user to edit!")
            return
            
        row = selected[0].row()
        username = self.userTable.item(row, 0).text()
        
        import sqlite3
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT password, role, staff_name, mobile_number FROM users WHERE username=?", (username,))
        user_data = cursor.fetchone()
        conn.close()
        
        if not user_data:
            return
            
        current_role = getattr(self.window(), 'current_role', '1')
        dialog = EditUserDialog(current_role, user_data, username, self)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    UPDATE users 
                    SET password=?, role=?, staff_name=?, mobile_number=?
                    WHERE username=?
                ''', (data['password'], data['role'], data['staff_name'], data['mobile_number'], username))
                conn.commit()
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(self, "Success", "User updated successfully!")
                self.load_users()
            finally:
                conn.close()

    def delete_user_prompt(self):
        selected = self.userTable.selectionModel().selectedRows()
        if not selected:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Warning", "Please select a user to delete!")
            return
            
        username = self.userTable.item(selected[0].row(), 0).text()
        
        if username == "notioff" or username == "admin":
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Denied", "Cannot delete the default superuser!")
            return
            
        from PyQt6.QtWidgets import QMessageBox
        confirm = QMessageBox.question(self, "Confirm", f"Are you sure you want to delete {username}?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                                     
        if confirm == QMessageBox.StandardButton.Yes:
            import sqlite3
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE username=?", (username,))
            conn.commit()
            conn.close()
            self.load_users()
            QMessageBox.information(self, "Success", "User deleted successfully!")

    def load_purchase_orders(self):
        if not hasattr(self, 'poTable'): return
        import sqlite3
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT po_number, created_by, date, vendor_id, vendor_name, total_qty, total_amount FROM purchase_orders ORDER BY id DESC")
        pos = cursor.fetchall()
        conn.close()
        
        self.poTable.setRowCount(len(pos))
        for row, po in enumerate(pos):
            self.poTable.setItem(row, 0, QTableWidgetItem(str(po[0])))
            self.poTable.setItem(row, 1, QTableWidgetItem(str(po[1])))
            self.poTable.setItem(row, 2, QTableWidgetItem(str(po[2])))
            self.poTable.setItem(row, 3, QTableWidgetItem(str(po[3])))
            self.poTable.setItem(row, 4, QTableWidgetItem(str(po[4])))
            self.poTable.setItem(row, 5, QTableWidgetItem(str(po[5])))
            self.poTable.setItem(row, 6, QTableWidgetItem(f"{po[6]:.2f} Dhs"))

    def new_po_prompt(self):
        current_username = getattr(self.window(), 'current_username', 'admin')
        dialog = NewPODialog(current_username, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_purchase_orders()
        
    def edit_po_prompt(self):
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Purchase Order", "Edit PO Screen coming soon!")
        
    def save_po_prompt(self):
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Purchase Order", "Please use 'New' to create and save a PO.")
        
    def delete_po_prompt(self):
        selected = self.poTable.selectionModel().selectedRows()
        if not selected:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Warning", "Please select a PO to delete!")
            return
            
        po_num = self.poTable.item(selected[0].row(), 0).text()
        from PyQt6.QtWidgets import QMessageBox
        confirm = QMessageBox.question(self, "Confirm", f"Delete {po_num}?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if confirm == QMessageBox.StandardButton.Yes:
            import sqlite3
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM purchase_order_items WHERE po_id IN (SELECT id FROM purchase_orders WHERE po_number=?)", (po_num,))
            cursor.execute("DELETE FROM purchase_orders WHERE po_number=?", (po_num,))
            conn.commit()
            conn.close()
            self.load_purchase_orders()
            QMessageBox.information(self, "Success", "PO Deleted!")

    def load_items(self):
        if not hasattr(self, 'itemTable'): return
        
        import sqlite3
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT item_number, barcode, product_name, description, purchase_price, sale_price, stock FROM products")
        items = cursor.fetchall()
        conn.close()
        
        self.itemTable.setRowCount(len(items))
        for row, it in enumerate(items):
            self.itemTable.setItem(row, 0, QTableWidgetItem(str(it[0])))
            self.itemTable.setItem(row, 1, QTableWidgetItem(str(it[1])))
            self.itemTable.setItem(row, 2, QTableWidgetItem(str(it[2])))
            self.itemTable.setItem(row, 3, QTableWidgetItem(str(it[3]).replace('\n', ' ')))
            self.itemTable.setItem(row, 4, QTableWidgetItem(f"{it[4]:.2f} Dhs"))
            self.itemTable.setItem(row, 5, QTableWidgetItem(f"{it[5]:.2f} Dhs"))
            self.itemTable.setItem(row, 6, QTableWidgetItem(str(it[6])))

    def new_item_prompt(self):
        dialog = NewItemDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if not data['product_name']:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Error", "Product Name is required!")
                return
                
            import sqlite3
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO products (item_number, barcode, product_name, description, purchase_price, sale_price, stock)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (data['item_number'], data['barcode'], data['product_name'], data['description'], data['purchase_price'], data['sale_price'], 0))
                conn.commit()
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(self, "Success", "Item added successfully!")
                self.load_items()
            except sqlite3.IntegrityError:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Error", "Item Number or Barcode already exists!")
            finally:
                conn.close()
                
    def edit_item_prompt(self):
        selected = self.itemTable.selectionModel().selectedRows()
        if not selected:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Warning", "Please select an item to edit!")
            return
            
        row = selected[0].row()
        item_no = self.itemTable.item(row, 0).text()
        
        import sqlite3
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT item_number, barcode, product_name, description, purchase_price, sale_price, stock FROM products WHERE item_number=?", (item_no,))
        item_data = cursor.fetchone()
        conn.close()
        
        if not item_data:
            return
            
        current_role = getattr(self.window(), 'current_role', '1')
        dialog = EditItemDialog(current_role, item_data, self)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if not data['product_name']:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Error", "Product Name cannot be empty!")
                return
                
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    UPDATE products 
                    SET barcode=?, product_name=?, description=?, purchase_price=?, sale_price=?
                    WHERE item_number=?
                ''', (data['barcode'], data['product_name'], data['description'], data['purchase_price'], data['sale_price'], item_no))
                conn.commit()
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(self, "Success", "Item updated successfully!")
                self.load_items()
            finally:
                conn.close()

    def load_vendors(self):
        if not hasattr(self, 'vendorTable'): return
        
        import sqlite3
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT vendor_id, vendor_name FROM vendor ORDER BY vendor_name ASC")
        vendors = cursor.fetchall()
        conn.close()
        
        self.vendorTable.setRowCount(len(vendors))
        for row, v in enumerate(vendors):
            self.vendorTable.setItem(row, 0, QTableWidgetItem(str(v[0])))
            self.vendorTable.setItem(row, 1, QTableWidgetItem(str(v[1])))

    def new_vendor_prompt(self):
        dialog = NewVendorDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if not data['vendor_id'] or not data['vendor_name']:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Error", "Vendor ID and Name are required!")
                return
                
            import sqlite3
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO vendor (vendor_id, vendor_name) VALUES (?, ?)", (data['vendor_id'], data['vendor_name']))
                conn.commit()
                self.load_vendors()
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(self, "Success", "Vendor added successfully!")
            except sqlite3.IntegrityError:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Error", "Vendor ID already exists!")
            finally:
                conn.close()

    def edit_vendor_prompt(self):
        selected = self.vendorTable.selectionModel().selectedRows()
        if not selected:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Warning", "Please select a vendor to edit!")
            return
            
        row = selected[0].row()
        vendor_id = self.vendorTable.item(row, 0).text()
        vendor_name = self.vendorTable.item(row, 1).text()
        
        dialog = EditVendorDialog(vendor_id, vendor_name, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if not data['vendor_name']:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Error", "Vendor Name is required!")
                return
                
            import sqlite3
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("UPDATE vendor SET vendor_name=? WHERE vendor_id=?", (data['vendor_name'], vendor_id))
            conn.commit()
            conn.close()
            self.load_vendors()
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Success", "Vendor updated successfully!")

    def delete_vendor_prompt(self):
        selected = self.vendorTable.selectionModel().selectedRows()
        if not selected:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Warning", "Please select a vendor to delete!")
            return
            
        vendor_id = self.vendorTable.item(selected[0].row(), 0).text()
        vendor_name = self.vendorTable.item(selected[0].row(), 1).text()
        
        from PyQt6.QtWidgets import QMessageBox
        confirm = QMessageBox.question(self, "Confirm", f"Are you sure you want to permanently delete {vendor_name} ({vendor_id})?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if confirm == QMessageBox.StandardButton.Yes:
            import sqlite3
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM vendor WHERE vendor_id=?", (vendor_id,))
            conn.commit()
            conn.close()
            self.load_vendors()
            QMessageBox.information(self, "Success", "Vendor deleted successfully!")

    def delete_item_prompt(self):
        selected = self.itemTable.selectionModel().selectedRows()
        if not selected:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Warning", "Please select an item to delete!")
            return
            
        item_no = self.itemTable.item(selected[0].row(), 0).text()
        item_name = self.itemTable.item(selected[0].row(), 2).text()
        
        from PyQt6.QtWidgets import QMessageBox
        confirm = QMessageBox.question(self, "Confirm", f"Are you sure you want to permanently delete {item_no} ({item_name})?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            import sqlite3
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM products WHERE item_number=?", (item_no,))
            conn.commit()
            conn.close()
            self.load_items()
            QMessageBox.information(self, "Success", "Item deleted successfully!")

    def switch_admin_page(self, index):
        self.adminStackedWidget.setCurrentIndex(index)
        
    def logout(self):
        self.stacked_widget.setCurrentIndex(0)

    def load_items(self):
        if not hasattr(self, 'itemTable'): return
        
        import sqlite3
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT item_number, barcode, product_name, description, purchase_price, sale_price, stock FROM products")
        items = cursor.fetchall()
        conn.close()
        
        self.itemTable.setRowCount(len(items))
        for row, it in enumerate(items):
            self.itemTable.setItem(row, 0, QTableWidgetItem(str(it[0])))
            self.itemTable.setItem(row, 1, QTableWidgetItem(str(it[1])))
            self.itemTable.setItem(row, 2, QTableWidgetItem(str(it[2])))
            self.itemTable.setItem(row, 3, QTableWidgetItem(str(it[3]).replace('\n', ' ')))
            self.itemTable.setItem(row, 4, QTableWidgetItem(f"{it[4]:.2f} Dhs"))
            self.itemTable.setItem(row, 5, QTableWidgetItem(f"{it[5]:.2f} Dhs"))
            self.itemTable.setItem(row, 6, QTableWidgetItem(str(it[6])))

    def new_item_prompt(self):
        dialog = NewItemDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if not data['product_name']:
                QMessageBox.warning(self, "Error", "Product Name is required!")
                return
                
            import sqlite3
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO products (item_number, barcode, product_name, description, purchase_price, sale_price, stock)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (data['item_number'], data['barcode'], data['product_name'], data['description'], data['purchase_price'], data['sale_price'], 0))
                conn.commit()
                QMessageBox.information(self, "Success", "Item added successfully!")
                self.load_items()
            except sqlite3.IntegrityError:
                QMessageBox.warning(self, "Error", "Item Number or Barcode already exists!")
            finally:
                conn.close()

class NewItemDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Item")
        self.setMinimumWidth(400)
        
        layout = QFormLayout(self)
        
        self.item_number_input = QLineEdit()
        self.item_number_input.setReadOnly(True)
        self.item_number_input.setStyleSheet("background-color: #f0f0f0; color: black;")
        
        self.barcode_input = QLineEdit()
        self.product_name_input = QLineEdit()
        
        from PyQt6.QtWidgets import QTextEdit
        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("Top Category\nMain Category\nSub Category\nDescription")
        self.description_input.setMaximumHeight(80)
        
        self.purchase_price_input = QLineEdit()
        self.purchase_price_input.setPlaceholderText("0.00")
        
        self.sale_price_input = QLineEdit()
        self.sale_price_input.setPlaceholderText("0.00")
        
        self.soh_input = QLineEdit("0")
        self.soh_input.setReadOnly(True)
        self.soh_input.setStyleSheet("background-color: #f0f0f0; color: black;")
        
        layout.addRow("Item Number:", self.item_number_input)
        layout.addRow("Barcode:", self.barcode_input)
        layout.addRow("Item Name:", self.product_name_input)
        layout.addRow("Description:", self.description_input)
        layout.addRow("Cost Price:", self.purchase_price_input)
        layout.addRow("Selling Price:", self.sale_price_input)
        layout.addRow("SOH (Stock):", self.soh_input)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addRow(self.buttons)
        
        self.generate_item_number()
        
    def generate_item_number(self):
        import sqlite3
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT item_number FROM products ORDER BY id DESC LIMIT 1")
        last_item = cursor.fetchone()
        conn.close()
        
        if last_item and last_item[0].startswith("01-"):
            try:
                num = int(last_item[0].split("-")[1])
                new_num = num + 1
                self.item_number_input.setText(f"01-{new_num:07d}")
            except:
                self.item_number_input.setText("01-0000001")
        else:
            self.item_number_input.setText("01-0000001")
            
    def get_data(self):
        try:
            cost = float(self.purchase_price_input.text())
        except ValueError:
            cost = 0.0
            
        try:
            sell = float(self.sale_price_input.text())
        except ValueError:
            sell = 0.0
            
        return {
            "item_number": self.item_number_input.text(),
            "barcode": self.barcode_input.text(),
            "product_name": self.product_name_input.text(),
            "description": self.description_input.toPlainText(),
            "purchase_price": cost,
            "sale_price": sell
        }
        
    def edit_item_prompt(self):
        QMessageBox.information(self, "Item Menu", "Edit Item Dialog coming soon!")
        
    def load_vendors(self):
        if not hasattr(self, 'vendorTable'): return
        
        import sqlite3
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT vendor_id, vendor_name FROM vendor ORDER BY vendor_name ASC")
        vendors = cursor.fetchall()
        conn.close()
        
        self.vendorTable.setRowCount(len(vendors))
        for row, v in enumerate(vendors):
            self.vendorTable.setItem(row, 0, QTableWidgetItem(str(v[0])))
            self.vendorTable.setItem(row, 1, QTableWidgetItem(str(v[1])))

    def new_vendor_prompt(self):
        dialog = NewVendorDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if not data['vendor_id'] or not data['vendor_name']:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Error", "Vendor ID and Name are required!")
                return
                
            import sqlite3
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO vendor (vendor_id, vendor_name) VALUES (?, ?)", (data['vendor_id'], data['vendor_name']))
                conn.commit()
                self.load_vendors()
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(self, "Success", "Vendor added successfully!")
            except sqlite3.IntegrityError:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Error", "Vendor ID already exists!")
            finally:
                conn.close()

    def edit_vendor_prompt(self):
        selected = self.vendorTable.selectionModel().selectedRows()
        if not selected:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Warning", "Please select a vendor to edit!")
            return
            
        row = selected[0].row()
        vendor_id = self.vendorTable.item(row, 0).text()
        vendor_name = self.vendorTable.item(row, 1).text()
        
        dialog = EditVendorDialog(vendor_id, vendor_name, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if not data['vendor_name']:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Error", "Vendor Name is required!")
                return
                
            import sqlite3
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("UPDATE vendor SET vendor_name=? WHERE vendor_id=?", (data['vendor_name'], vendor_id))
            conn.commit()
            conn.close()
            self.load_vendors()
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Success", "Vendor updated successfully!")

    def delete_vendor_prompt(self):
        selected = self.vendorTable.selectionModel().selectedRows()
        if not selected:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Warning", "Please select a vendor to delete!")
            return
            
        vendor_id = self.vendorTable.item(selected[0].row(), 0).text()
        vendor_name = self.vendorTable.item(selected[0].row(), 1).text()
        
        from PyQt6.QtWidgets import QMessageBox
        confirm = QMessageBox.question(self, "Confirm", f"Are you sure you want to permanently delete {vendor_name} ({vendor_id})?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if confirm == QMessageBox.StandardButton.Yes:
            import sqlite3
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM vendor WHERE vendor_id=?", (vendor_id,))
            conn.commit()
            conn.close()
            self.load_vendors()
            QMessageBox.information(self, "Success", "Vendor deleted successfully!")

    def delete_item_prompt(self):
        selected = self.itemTable.selectionModel().selectedRows()
        if not selected:
            QMessageBox.warning(self, "Warning", "Please select an item to delete!")
            return
            
        item_no = self.itemTable.item(selected[0].row(), 0).text()
        item_name = self.itemTable.item(selected[0].row(), 2).text()
        
        confirm = QMessageBox.question(self, "Confirm", f"Are you sure you want to permanently delete {item_no} ({item_name})?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            import sqlite3
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM products WHERE item_number=?", (item_no,))
            conn.commit()
            conn.close()
            self.load_items()
            QMessageBox.information(self, "Success", "Item deleted successfully!")

    def load_purchase_orders(self):
        if not hasattr(self, 'poTable'): return
        
        import sqlite3
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT po_number, created_by, date, vendor_id, vendor_name, total_qty, total_amount FROM purchase_orders ORDER BY id DESC")
        pos = cursor.fetchall()
        conn.close()
        
        self.poTable.setRowCount(len(pos))
        for row, po in enumerate(pos):
            self.poTable.setItem(row, 0, QTableWidgetItem(str(po[0])))
            self.poTable.setItem(row, 1, QTableWidgetItem(str(po[1])))
            self.poTable.setItem(row, 2, QTableWidgetItem(str(po[2])))
            self.poTable.setItem(row, 3, QTableWidgetItem(str(po[3])))
            self.poTable.setItem(row, 4, QTableWidgetItem(str(po[4])))
            self.poTable.setItem(row, 5, QTableWidgetItem(str(po[5])))
            self.poTable.setItem(row, 6, QTableWidgetItem(f"{po[6]:.2f} Dhs"))

    def new_po_prompt(self):
        current_username = getattr(self.window(), 'current_username', 'admin')
        dialog = NewPODialog(current_username, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_purchase_orders()
        
    def edit_po_prompt(self):
        QMessageBox.information(self, "Purchase Order", "Edit PO Screen coming soon!")
        
    def save_po_prompt(self):
        QMessageBox.information(self, "Purchase Order", "Please use 'New' to create and save a PO.")
        
    def delete_po_prompt(self):
        selected = self.poTable.selectionModel().selectedRows()
        if not selected:
            QMessageBox.warning(self, "Warning", "Please select a PO to delete!")
            return
            
        po_num = self.poTable.item(selected[0].row(), 0).text()
        confirm = QMessageBox.question(self, "Confirm", f"Delete {po_num}?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if confirm == QMessageBox.StandardButton.Yes:
            import sqlite3
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM purchase_order_items WHERE po_id IN (SELECT id FROM purchase_orders WHERE po_number=?)", (po_num,))
            cursor.execute("DELETE FROM purchase_orders WHERE po_number=?", (po_num,))
            conn.commit()
            conn.close()
            self.load_purchase_orders()
            QMessageBox.information(self, "Success", "PO Deleted!")

    def _placeholder(self):
        pass
        current_role = getattr(self.window(), 'current_role', '1')
        dialog = AddUserDialog(current_role, self)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if not data['username'] or not data['password']:
                QMessageBox.warning(self, "Error", "Username and Password are required!")
                return
            
            # Automatically set joining date to today
            today_str = datetime.datetime.now().strftime('%d.%m.%Y')
            
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO users (username, password, role, staff_name, mobile_number, joining_date)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (data['username'], data['password'], data['role'], data['staff_name'], data['mobile_number'], today_str))
                conn.commit()
                QMessageBox.information(self, "Success", "User added successfully!")
                self.load_users()  # Refresh the table
            except sqlite3.IntegrityError:
                QMessageBox.warning(self, "Error", "Username already exists!")
            finally:
                conn.close()

# The Popup Dialog Class for adding a user
class AddUserDialog(QDialog):
    def __init__(self, current_role, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New User")
        self.setMinimumWidth(300)
        self.current_role = current_role
        
        layout = QFormLayout(self)
        
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.staffname_input = QLineEdit()
        self.mobile_input = QLineEdit()
        
        self.role_combo = QComboBox()
        # Superuser (2) can create all roles. Manager (1) can ONLY create Cashiers (0).
        if self.current_role == "2":
            self.role_combo.addItems(["0 (Cashier)", "1 (Manager)", "2 (Superuser)"])
        else:
            self.role_combo.addItems(["0 (Cashier)"])
            
        layout.addRow("Username:", self.username_input)
        layout.addRow("Password:", self.password_input)
        layout.addRow("Staff Name:", self.staffname_input)
        layout.addRow("Mobile Number:", self.mobile_input)
        layout.addRow("IDGrade (Role):", self.role_combo)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addRow(self.buttons)
        
    def get_data(self):
        # Extract just the number (0, 1, or 2) from the dropdown selection
        selected_role = self.role_combo.currentText().split(" ")[0]
        return {
            "username": self.username_input.text(),
            "password": self.password_input.text(),
            "staff_name": self.staffname_input.text(),
            "mobile_number": self.mobile_input.text(),
            "role": selected_role
        }
# Back out of AddUserDialog class, these belong to AdminWindow:

# Because the script replacement put these functions inside the AddUserDialog class

    def delete_user_prompt(self):
        selected = self.userTable.selectionModel().selectedRows()
        if not selected:
            QMessageBox.warning(self, "Warning", "Please select a user to delete!")
            return
            
        username = self.userTable.item(selected[0].row(), 0).text()
        
        if username == "notioff" or username == "admin":
            QMessageBox.warning(self, "Denied", "Cannot delete the default superuser!")
            return
            
        confirm = QMessageBox.question(self, "Confirm", f"Are you sure you want to delete {username}?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                                     
        if confirm == QMessageBox.StandardButton.Yes:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE username=?", (username,))
            conn.commit()
            conn.close()
            self.load_users()
            QMessageBox.information(self, "Success", "User deleted successfully!")

    def edit_user_prompt(self):
        selected = self.userTable.selectionModel().selectedRows()
        if not selected:
            QMessageBox.warning(self, "Warning", "Please select a user to edit!")
            return
            
        row = selected[0].row()
        username = self.userTable.item(row, 0).text()
        
        # Fetch current details
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT password, role, staff_name, mobile_number FROM users WHERE username=?", (username,))
        user_data = cursor.fetchone()
        conn.close()
        
        if not user_data:
            return
            
        current_role = getattr(self.window(), 'current_role', '1')
        dialog = EditUserDialog(current_role, user_data, username, self)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            
            # Save updates
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    UPDATE users 
                    SET password=?, role=?, staff_name=?, mobile_number=?
                    WHERE username=?
                ''', (data['password'], data['role'], data['staff_name'], data['mobile_number'], username))
                conn.commit()
                QMessageBox.information(self, "Success", "User updated successfully!")
                self.load_users()
            finally:
                conn.close()

class EditUserDialog(QDialog):
    def __init__(self, current_role, user_data, username, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edit User: {username}")
        self.setMinimumWidth(300)
        self.current_role = current_role
        
        layout = QFormLayout(self)
        
        # user_data is (password, role, staff_name, mobile_number)
        self.password_input = QLineEdit(user_data[0])
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.staffname_input = QLineEdit(user_data[2])
        self.mobile_input = QLineEdit(user_data[3])
        
        self.role_combo = QComboBox()
        self.role_combo.addItems(["0 (Cashier)", "1 (Manager)", "2 (Superuser)"])
        
        # Set dropdown to their current role
        for i in range(self.role_combo.count()):
            if self.role_combo.itemText(i).startswith(user_data[1]):
                self.role_combo.setCurrentIndex(i)
                break
                
        # If logged in user is NOT superuser (2), disable editing the role completely
        if self.current_role != "2":
            self.role_combo.setEnabled(False)
            
        layout.addRow("Password:", self.password_input)
        layout.addRow("Staff Name:", self.staffname_input)
        layout.addRow("Mobile Number:", self.mobile_input)
        layout.addRow("IDGrade (Role):", self.role_combo)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addRow(self.buttons)
        
    def get_data(self):
        selected_role = self.role_combo.currentText().split(" ")[0]
        return {
            "password": self.password_input.text(),
            "staff_name": self.staffname_input.text(),
            "mobile_number": self.mobile_input.text(),
            "role": selected_role
        }
# I am re-adding them to the AdminWindow class properly by dedenting them.





class NewPODialog(QDialog):
    def __init__(self, username, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Purchase Order")
        self.setMinimumSize(800, 600)
        self.username = username
        self.pdf_path = ""
        self.po_items = []  # Store added items
        
        # Load Products for AutoComplete
        import sqlite3
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        # The products table lacks vendor info, so we select what we have
        cursor.execute("SELECT item_number, barcode, product_name, purchase_price FROM products")
        self.products_db = cursor.fetchall()
        
        cursor.execute("SELECT vendor_id, vendor_name FROM vendor ORDER BY vendor_name ASC")
        self.vendors_db = cursor.fetchall()
        conn.close()
        
        self.vendor_search_list = []
        self.vendor_map = {}
        for v in self.vendors_db:
            key = f"{v[0]} | {v[1]}"
            if key not in self.vendor_map:
                self.vendor_search_list.append(key)
                self.vendor_map[key] = {"vendor_id": str(v[0]), "vendor_name": str(v[1])}
        
        # Build search list: "ItemNo | Barcode | Name"
        self.search_list = []
        self.product_map = {}
        for p in self.products_db:
            key = f"{p[0]} | {p[1]} | {p[2]}"
            self.search_list.append(key)
            self.product_map[key] = {
                "item_number": p[0], "barcode": p[1], "product_name": p[2], 
                "cost": p[3], "vendor_id": "", "vendor_name": ""
            }
            
        self.init_ui()
        self.generate_po_number()
        
    def init_ui(self):
        from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QFormLayout, QTableWidget, QTableWidgetItem, QHeaderView, QLabel, QLineEdit, QPushButton, QComboBox
        from PyQt6.QtCore import Qt
        
        main_layout = QVBoxLayout(self)
        
        # --- HEADER ---
        header_layout = QFormLayout()
        
        self.po_num_input = QLineEdit()
        self.po_num_input.setReadOnly(True)
        self.po_num_input.setStyleSheet("background-color: #f0f0f0; color: black;")
        
        self.by_input = QLineEdit(self.username)
        self.by_input.setReadOnly(True)
        self.by_input.setStyleSheet("background-color: #f0f0f0; color: black;")
        
        today = datetime.datetime.now().strftime('%d.%m.%Y')
        self.date_input = QLineEdit(today)
        self.date_input.setReadOnly(True)
        self.date_input.setStyleSheet("background-color: #f0f0f0; color: black;")
        
        self.vendor_id_combo = QComboBox()
        self.vendor_id_combo.setEditable(True)
        self.vendor_id_combo.addItems([""] + self.vendor_search_list)
        
        completer_v = QCompleter(self.vendor_search_list)
        completer_v.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer_v.setFilterMode(Qt.MatchFlag.MatchContains)
        self.vendor_id_combo.setCompleter(completer_v)
        self.vendor_id_combo.currentTextChanged.connect(self.lookup_vendor)
        
        self.vendor_name_input = QLineEdit()
        self.vendor_name_input.setReadOnly(True)
        self.vendor_name_input.setStyleSheet("background-color: #f0f0f0; color: black;")
        
        header_layout.addRow("PO Number:", self.po_num_input)
        header_layout.addRow("By:", self.by_input)
        header_layout.addRow("Date:", self.date_input)
        header_layout.addRow("Search Vendor:", self.vendor_id_combo)
        header_layout.addRow("Vendor Name:", self.vendor_name_input)
        main_layout.addLayout(header_layout)
        
        # --- ADD ITEM SECTION ---
        add_item_layout = QHBoxLayout()
        
        self.search_combo = QComboBox()
        self.search_combo.setEditable(True)
        self.search_combo.addItems(self.search_list)
        self.search_combo.setMinimumWidth(300)
        # Completer for smart search
        completer = QCompleter(self.search_list)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.search_combo.setCompleter(completer)
        
        self.qty_input = QLineEdit()
        self.qty_input.setPlaceholderText("Qty")
        self.qty_input.setMaximumWidth(80)
        
        add_btn = QPushButton("Add Item")
        add_btn.setStyleSheet("background-color: #3498db; color: white; font-weight: bold;")
        add_btn.clicked.connect(self.add_item_to_table)
        
        add_item_layout.addWidget(QLabel("Search Product:"))
        add_item_layout.addWidget(self.search_combo)
        add_item_layout.addWidget(self.qty_input)
        add_item_layout.addWidget(add_btn)
        main_layout.addLayout(add_item_layout)
        
        # --- ITEMS TABLE ---
        self.items_table = QTableWidget()
        self.items_table.setColumnCount(6)
        self.items_table.setHorizontalHeaderLabels(["Item Number", "Barcode", "Product Name", "Cost Price", "Qty", "Total"])
        self.items_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.items_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.items_table.setStyleSheet("color: black; background-color: white;")
        main_layout.addWidget(self.items_table)
        
        # --- FOOTER ---
        footer_layout = QHBoxLayout()
        
        self.attach_btn = QPushButton("Attach Invoice PDF")
        self.attach_btn.clicked.connect(self.attach_pdf)
        self.pdf_label = QLabel("No file attached")
        
        self.total_lbl = QLabel("Total Amount: 0.00 Dhs")
        self.total_lbl.setStyleSheet("font-weight: bold; font-size: 16px; color: #e74c3c;")
        
        save_btn = QPushButton("Save Purchase Order")
        save_btn.setStyleSheet("background-color: #27ae60; color: white; padding: 10px; font-weight: bold;")
        save_btn.clicked.connect(self.save_po)
        
        footer_layout.addWidget(self.attach_btn)
        footer_layout.addWidget(self.pdf_label)
        footer_layout.addStretch()
        footer_layout.addWidget(self.total_lbl)
        footer_layout.addWidget(save_btn)
        main_layout.addLayout(footer_layout)

    def generate_po_number(self):
        import sqlite3
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT po_number FROM purchase_orders ORDER BY id DESC LIMIT 1")
        last_po = cursor.fetchone()
        conn.close()
        
        if last_po and last_po[0].startswith("PO-"):
            try:
                num = int(last_po[0].split("-")[1])
                new_num = num + 1
                self.po_num_input.setText(f"PO-{new_num:07d}")
            except:
                self.po_num_input.setText("PO-0000001")
        else:
            self.po_num_input.setText("PO-0000001")
            
    def lookup_vendor(self):
        selection = self.vendor_id_combo.currentText().strip()
        if not selection:
            self.vendor_name_input.clear()
            return
            
        if selection in self.vendor_map:
            self.vendor_name_input.setText(self.vendor_map[selection]['vendor_name'])
        else:
            import sqlite3
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT vendor_name FROM vendor WHERE vendor_id=? LIMIT 1", (selection,))
            res = cursor.fetchone()
            conn.close()
            
            if res and res[0]:
                self.vendor_name_input.setText(res[0])
            else:
                self.vendor_name_input.clear()

    def add_item_to_table(self):
        from PyQt6.QtWidgets import QTableWidgetItem, QMessageBox
        selection = self.search_combo.currentText()
        if selection not in self.product_map:
            QMessageBox.warning(self, "Error", "Please select a valid product from the dropdown!")
            return
            
        try:
            qty = int(self.qty_input.text())
            if qty <= 0: raise ValueError
        except:
            QMessageBox.warning(self, "Error", "Please enter a valid positive quantity!")
            return
            
        prod = self.product_map[selection]
        
        # If vendor is empty, autofill it from the first selected product
        if not self.vendor_id_combo.currentText() and prod['vendor_id']:
            key = f"{prod['vendor_id']} | {prod['vendor_name']}"
            self.vendor_id_combo.setCurrentText(key)
            
        cost = float(prod['cost']) if prod['cost'] else 0.0
        total = cost * qty
        
        item_dict = {
            "item_number": prod['item_number'],
            "barcode": prod['barcode'],
            "product_name": prod['product_name'],
            "cost_price": cost,
            "qty": qty,
            "total": total
        }
        self.po_items.append(item_dict)
        
        # Update Table UI
        row = self.items_table.rowCount()
        self.items_table.insertRow(row)
        self.items_table.setItem(row, 0, QTableWidgetItem(str(prod['item_number'])))
        self.items_table.setItem(row, 1, QTableWidgetItem(str(prod['barcode'])))
        self.items_table.setItem(row, 2, QTableWidgetItem(str(prod['product_name'])))
        self.items_table.setItem(row, 3, QTableWidgetItem(f"{cost:.2f}"))
        self.items_table.setItem(row, 4, QTableWidgetItem(str(qty)))
        self.items_table.setItem(row, 5, QTableWidgetItem(f"{total:.2f}"))
        
        self.qty_input.clear()
        self.update_totals()
        
    def update_totals(self):
        total_amt = sum(item['total'] for item in self.po_items)
        self.total_lbl.setText(f"Total Amount: {total_amt:.2f} Dhs")
        
    def attach_pdf(self):
        from PyQt6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Invoice PDF", "", "PDF Files (*.pdf)")
        if file_path:
            self.pdf_path = file_path
            self.pdf_label.setText(file_path.split("/")[-1])
            
    def save_po(self):
        from PyQt6.QtWidgets import QMessageBox
        if not self.po_items:
            QMessageBox.warning(self, "Error", "Cannot save an empty Purchase Order!")
            return
            
        po_number = self.po_num_input.text()
        created_by = self.by_input.text()
        date_str = self.date_input.text()
        vendor_text = self.vendor_id_combo.currentText().strip()
        vendor_id = self.vendor_map[vendor_text]['vendor_id'] if vendor_text in self.vendor_map else vendor_text
        vendor_name = self.vendor_name_input.text()
        
        total_qty = sum(item['qty'] for item in self.po_items)
        total_amt = sum(item['total'] for item in self.po_items)
        
        import sqlite3
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        try:
            # 1. Insert into purchase_orders
            cursor.execute('''
                INSERT INTO purchase_orders (po_number, created_by, date, vendor_id, vendor_name, total_qty, total_amount, invoice_pdf)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (po_number, created_by, date_str, vendor_id, vendor_name, total_qty, total_amt, self.pdf_path))
            
            po_id = cursor.lastrowid
            
            # 2. Insert into purchase_order_items and Update Stock
            for item in self.po_items:
                cursor.execute('''
                    INSERT INTO purchase_order_items (po_id, item_number, barcode, product_name, cost_price, qty, total)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (po_id, item['item_number'], item['barcode'], item['product_name'], item['cost_price'], item['qty'], item['total']))
                
                # Update the stock in products table
                cursor.execute('''
                    UPDATE products SET stock = stock + ? WHERE item_number = ?
                ''', (item['qty'], item['item_number']))
                
            conn.commit()
            QMessageBox.information(self, "Success", f"Purchase Order {po_number} saved successfully!")
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save PO: {str(e)}")
        finally:
            conn.close()



class NewVendorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Vendor")
        self.setMinimumWidth(300)
        
        from PyQt6.QtWidgets import QFormLayout, QLineEdit, QDialogButtonBox
        layout = QFormLayout(self)
        
        self.vendor_id_input = QLineEdit()
        self.vendor_name_input = QLineEdit()
        
        layout.addRow("Vendor ID (e.g. 0000001):", self.vendor_id_input)
        layout.addRow("Vendor Name:", self.vendor_name_input)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addRow(self.buttons)
        
    def get_data(self):
        vid = self.vendor_id_input.text().strip()
        # Automatically pad with zeros if they just type a number like "15"
        if vid.isdigit():
            vid = vid.zfill(7)
            
        return {
            "vendor_id": vid,
            "vendor_name": self.vendor_name_input.text().strip()
        }

class EditVendorDialog(QDialog):
    def __init__(self, vendor_id, vendor_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edit Vendor: {vendor_id}")
        self.setMinimumWidth(300)
        
        from PyQt6.QtWidgets import QFormLayout, QLineEdit, QDialogButtonBox
        layout = QFormLayout(self)
        
        self.vendor_id_input = QLineEdit(vendor_id)
        self.vendor_id_input.setReadOnly(True)
        self.vendor_id_input.setStyleSheet("background-color: #f0f0f0; color: black;")
        
        self.vendor_name_input = QLineEdit(vendor_name)
        
        layout.addRow("Vendor ID:", self.vendor_id_input)
        layout.addRow("Vendor Name:", self.vendor_name_input)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addRow(self.buttons)
        
    def get_data(self):
        return {
            "vendor_name": self.vendor_name_input.text().strip()
        }

class EditItemDialog(QDialog):
    def __init__(self, current_role, item_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edit Item: {item_data[0]}")
        self.setMinimumWidth(400)
        self.current_role = current_role
        
        from PyQt6.QtWidgets import QFormLayout, QLineEdit, QTextEdit, QDialogButtonBox
        layout = QFormLayout(self)
        
        self.item_number_input = QLineEdit(str(item_data[0]))
        self.item_number_input.setReadOnly(True)
        self.item_number_input.setStyleSheet("background-color: #f0f0f0; color: black;")
        
        self.barcode_input = QLineEdit(str(item_data[1]))
        self.product_name_input = QLineEdit(str(item_data[2]))
        
        self.description_input = QTextEdit()
        self.description_input.setText(str(item_data[3]))
        self.description_input.setMaximumHeight(80)
        
        self.purchase_price_input = QLineEdit(f"{float(item_data[4]):.2f}")
        self.sale_price_input = QLineEdit(f"{float(item_data[5]):.2f}")
        
        # Only Superuser (IDGrade 2) can edit the Cost/Sale Price
        if self.current_role != "2":
            self.purchase_price_input.setReadOnly(True)
            self.purchase_price_input.setStyleSheet("background-color: #f0f0f0; color: black;")
            self.sale_price_input.setReadOnly(True)
            self.sale_price_input.setStyleSheet("background-color: #f0f0f0; color: black;")
            
        self.soh_input = QLineEdit(str(item_data[6]))
        self.soh_input.setReadOnly(True)
        self.soh_input.setStyleSheet("background-color: #f0f0f0; color: black;")
        
        layout.addRow("Item Number:", self.item_number_input)
        layout.addRow("Barcode:", self.barcode_input)
        layout.addRow("Item Name:", self.product_name_input)
        layout.addRow("Description:", self.description_input)
        layout.addRow("Cost Price:", self.purchase_price_input)
        layout.addRow("Selling Price:", self.sale_price_input)
        layout.addRow("SOH (Stock):", self.soh_input)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addRow(self.buttons)
        
    def get_data(self):
        try:
            cost = float(self.purchase_price_input.text())
        except ValueError:
            cost = 0.0
            
        try:
            sell = float(self.sale_price_input.text())
        except ValueError:
            sell = 0.0
            
        return {
            "barcode": self.barcode_input.text(),
            "product_name": self.product_name_input.text(),
            "description": self.description_input.toPlainText(),
            "purchase_price": cost,
            "sale_price": sell
        }


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("POS System with PyQT6 & SQLite")
        self.setGeometry(100, 100, 1366, 768)
        self.setFixedSize(1366, 768)
        
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)
        
        # Initialize Screens
        self.login_screen = LoginWindow(self.stacked_widget)
        self.pos_screen = POSWindow(self.stacked_widget)
        self.admin_screen = AdminWindow(self.stacked_widget)
        
        self.stacked_widget.addWidget(self.login_screen)
        self.stacked_widget.addWidget(self.pos_screen)
        self.stacked_widget.addWidget(self.admin_screen)
        
        self.stacked_widget.setCurrentIndex(0)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
