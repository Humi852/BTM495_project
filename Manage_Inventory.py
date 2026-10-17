# Represents a general item with basic details.
class Item:
    def __init__(self, itemId, name, description, price):
        # Save the item's ID, name, description, and price.
        self.itemId = itemId
        self.name = name
        self.description = description
        self.price = price

    def getPrice(self):
        # Return the price of this item.
        return self.price


# A bicycle part is a type of Item with additional stock information.
class Part(Item):
    def __init__(self, itemId, name, description, price,
                 category, brand, stockQuantity):
        # Initialize the common Item attributes.
        super().__init__(itemId, name, description, price)
        # Save the part-specific details.
        self.category = category
        self.brand = brand
        self.stockQuantity = stockQuantity

    def checkStock(self):
        # Return the number of parts currently in stock.
        return self.stockQuantity


# Manages the collection of parts in the inventory.
class Inventory:
    def __init__(self, inventoryId):
        self.inventoryId = inventoryId
        self.items = {}  # Store parts by their item ID.

    def addItem(self, part):
        # Prevent adding another item with the same ID.
        if part.itemId in self.items:
            return "Item already exists."
        # Add the part to the inventory.
        self.items[part.itemId] = part
        return "Item added successfully."

    def updateItem(self, itemId, quantity):
        # Confirm that the item exists and the quantity is not negative.
        if itemId not in self.items or quantity < 0:
            return "Invalid item or quantity."
        # Update the part's stock quantity.
        self.items[itemId].stockQuantity = quantity
        return "Item updated successfully."

    def markOutOfStock(self, itemId):
        # Set the quantity to zero to mark the part as out of stock.
        return self.updateItem(itemId, 0)

    def checkStock(self, itemId):
        # Find the item and return its available quantity.
        if itemId in self.items:
            return self.items[itemId].checkStock()
        return "Item not found."
