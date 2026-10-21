from backend.models.item import Item


class Part(Item):
    def __init__(
        self,
        itemId: int,
        name: str,
        description: str,
        price: float,
        category: str,
        brand: str,
        stockQuantity: int,
    ) -> None:
        super().__init__(itemId, name, description, price)
        self.category = category
        self.brand = brand
        self.stockQuantity = stockQuantity

    def checkStock(self) -> int:
        return self.stockQuantity
