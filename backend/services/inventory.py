from backend.models.part import Part


class Inventory:
    def __init__(self, inventoryId: int) -> None:
        self.inventoryId = inventoryId
        self.items: dict[int, Part] = {}

    def addItem(self, part: Part) -> str:
        if part.itemId in self.items:
            return "Item already exists."
        self.items[part.itemId] = part
        return "Item added successfully."

    def updateItem(self, itemId: int, quantity: int) -> str:
        if itemId not in self.items or quantity < 0:
            return "Invalid item or quantity."
        self.items[itemId].stockQuantity = quantity
        return "Item updated successfully."

    def markOutOfStock(self, itemId: int) -> str:
        return self.updateItem(itemId, 0)

    def checkStock(self, itemId: int) -> int | str:
        if itemId in self.items:
            return self.items[itemId].checkStock()
        return "Item not found."
