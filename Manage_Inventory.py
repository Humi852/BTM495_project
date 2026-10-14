class Item:
    def __init__(self, itemId, name, description, price):
        self.itemId = itemId
        self.name = name
        self.description = description
        self.price = price

    def getPrice(self):
        return self.price


class Part(Item):
    def __init__(self, itemId, name, description, price,
                 category, brand, stockQuantity):
        super().__init__(itemId, name, description, price)
        self.category = category
        self.brand = brand
        self.stockQuantity = stockQuantity

    def checkStock(self):
        return self.stockQuantity


class Inventory:
    def __init__(self, inventoryId):
        self.inventoryId = inventoryId
        self.items = {}

    def addItem(self, part):
        if part.itemId in self.items:
            return "Item already exists."
        self.items[part.itemId] = part
        return "Item added successfully."

    def updateItem(self, itemId, quantity):
        if itemId not in self.items or quantity < 0:
            return "Invalid item or quantity."
        self.items[itemId].stockQuantity = quantity
        return "Item updated successfully."

    def markOutOfStock(self, itemId):
        return self.updateItem(itemId, 0)

    def checkStock(self, itemId):
        if itemId in self.items:
            return self.items[itemId].checkStock()
        return "Item not found."
