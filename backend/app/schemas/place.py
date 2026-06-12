from pydantic import BaseModel


class PlaceSchema(BaseModel):
    id: str
    name: str
    address: str
    lat: float
    lng: float
    category: str


class PlaceResponseSchema(BaseModel):
    places: list[PlaceSchema]
