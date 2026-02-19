"""
DB handler: one object created at app startup, passed around for all Mongo access.
Collection and keys are inferred from the Pydantic model type.

  db = get_db_handler()
  db.insert(UserRequirements, user_id="u1", data=req)
  db.get(UserRequirements, user_id="u1")
  db.update(UserRequirements, user_id="u1", data=req)
  db.delete(UserRequirements, user_id="u1")
  db.insert(DealershipContact, user_id="u1", dealer_id="d1", data=contact)
  db.find(DealershipContact, user_id="u1")
"""
from typing import Any, Optional, TypeVar

from pydantic import BaseModel

from app.models.documents import (
    UserRequirementsDocument,
    DealershipContactDocument,
    utc_now,
)
from app.models.schemas import UserRequirements, DealershipContact, DealerCar

# Registry: Pydantic model class -> (Beanie doc class, key field names)
_MODEL_REGISTRY: dict[type, tuple[type, list[str]]] = {
    UserRequirements: (UserRequirementsDocument, ["user_id"]),
    DealershipContact: (DealershipContactDocument, ["user_id", "dealer_id"]),
}

T = TypeVar("T", bound=BaseModel)


class DBHandler:
    """
    Single handler for Mongo access. Init once at startup after init_db().
    Use model type to route to the right collection and keys.
    """

    def _get_config(self, model_cls: type[BaseModel]) -> tuple[type, list[str]]:
        if model_cls not in _MODEL_REGISTRY:
            raise ValueError(f"Unknown model type for DB: {model_cls.__name__}. Register it in _MODEL_REGISTRY.")
        return _MODEL_REGISTRY[model_cls]

    def _key_query(self, model_cls: type[BaseModel], **key_fields: Any) -> dict[str, Any]:
        _, keys = self._get_config(model_cls)
        return {k: key_fields[k] for k in keys if k in key_fields}

    async def insert(self, model_cls: type[T], *, data: T, **key_fields: Any) -> T:
        """Insert one document. Keys (e.g. user_id, dealer_id) + data from Pydantic model."""
        doc_cls, key_names = self._get_config(model_cls)
        query = self._key_query(model_cls, **key_fields)
        if set(key_names) != set(query.keys()):
            raise ValueError(f"Missing key fields for {model_cls.__name__}: need {key_names}, got {list(key_fields)}")

        if model_cls is UserRequirements:
            doc = doc_cls(user_id=query["user_id"], requirements=data.model_dump())
        elif model_cls is DealershipContact:
            doc = doc_cls(
                user_id=query["user_id"],
                dealer_id=query["dealer_id"],
                dealership_name=data.dealership_name,
                address=data.address,
                distance_miles=data.distance_miles,
                status=data.status,
                cars=[c.model_dump() for c in data.cars],
            )
        else:
            raise ValueError(f"No insert mapping for {model_cls.__name__}")
        await doc.insert()
        return self._from_doc(model_cls, doc)

    async def get(self, model_cls: type[T], **key_fields: Any) -> Optional[T]:
        """Get one document by key fields. Returns None if not found."""
        doc_cls, _ = self._get_config(model_cls)
        query = self._key_query(model_cls, **key_fields)
        if not query:
            return None
        # Beanie find_one by query dict
        doc = await doc_cls.find_one(query)
        if not doc:
            return None
        return self._from_doc(model_cls, doc)

    async def update(self, model_cls: type[T], *, data: T, **key_fields: Any) -> T:
        """Upsert: update if exists, else insert."""
        doc_cls, key_names = self._get_config(model_cls)
        query = self._key_query(model_cls, **key_fields)
        if set(key_names) != set(query.keys()):
            raise ValueError(f"Missing key fields for {model_cls.__name__}: need {key_names}, got {list(key_fields)}")

        doc = await doc_cls.find_one(query)
        if model_cls is UserRequirements:
            if doc:
                doc.requirements = data.model_dump()
                doc.updated_at = utc_now()
                await doc.save()
            else:
                doc = doc_cls(user_id=query["user_id"], requirements=data.model_dump())
                await doc.insert()
        elif model_cls is DealershipContact:
            if doc:
                doc.dealership_name = data.dealership_name
                doc.address = data.address
                doc.distance_miles = data.distance_miles
                doc.status = data.status
                doc.cars = [c.model_dump() for c in data.cars]
                doc.updated_at = utc_now()
                await doc.save()
            else:
                doc = doc_cls(
                    user_id=query["user_id"],
                    dealer_id=query["dealer_id"],
                    dealership_name=data.dealership_name,
                    address=data.address,
                    distance_miles=data.distance_miles,
                    status=data.status,
                    cars=[c.model_dump() for c in data.cars],
                )
                await doc.insert()
        else:
            raise ValueError(f"No update mapping for {model_cls.__name__}")
        return self._from_doc(model_cls, doc)

    async def delete(self, model_cls: type[BaseModel], **key_fields: Any) -> bool:
        """Delete one document by key fields. Returns True if deleted, False if not found."""
        doc_cls, _ = self._get_config(model_cls)
        query = self._key_query(model_cls, **key_fields)
        doc = await doc_cls.find_one(query)
        if not doc:
            return False
        await doc.delete()
        return True

    async def find(self, model_cls: type[T], *, limit: int = 100, **key_fields: Any) -> list[T]:
        """Find many by key fields (e.g. all dealership contacts for a user_id)."""
        doc_cls, _ = self._get_config(model_cls)
        query = self._key_query(model_cls, **key_fields)
        cursor = doc_cls.find(query).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [self._from_doc(model_cls, d) for d in docs]

    def _from_doc(self, model_cls: type[T], doc: Any) -> T:
        if model_cls is UserRequirements:
            return model_cls.model_validate(doc.requirements)
        if model_cls is DealershipContact:
            return model_cls(
                user_id=doc.user_id,
                dealer_id=doc.dealer_id,
                dealership_name=doc.dealership_name,
                address=doc.address,
                distance_miles=doc.distance_miles,
                status=doc.status,
                cars=[DealerCar.model_validate(c) for c in doc.cars] if doc.cars else [],
            )
        raise ValueError(f"No from_doc for {model_cls.__name__}")