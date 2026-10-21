class Item:
    def __init__(
        self,
        itemId: int,
        name: str,
        description: str,
        price: float,
    ) -> None:
        self.itemId = itemId
        self.name = name
        self.description = description
        self.price = price

    def getPrice(self) -> float:
        return self.price


item = Item