"""Test MongoDB node result conversion."""

import asyncio
from unittest.mock import MagicMock, Mock, patch
from pymongo.results import (
    BulkWriteResult,
    DeleteResult,
    InsertManyResult,
    InsertOneResult,
    UpdateResult,
)
from orcheo.graph.state import State
from orcheo.nodes.mongodb import MongoDBNode


class TestMongoDBResultConversion:
    """Test MongoDB result conversion to dict/list[dict] format."""

    def setup_method(self):
        """Set up test fixtures."""
        # Mock MongoDB components to avoid requiring real connection
        self.mock_collection = MagicMock()
        self.mock_database = MagicMock()
        self.mock_database.__getitem__.return_value = self.mock_collection
        self.mock_client = MagicMock()
        self.mock_client.__getitem__.return_value = self.mock_database

    @patch("orcheo.nodes.mongodb.MongoClient")
    def test_convert_cursor_to_list_dict(self, mock_mongo_client):
        """Test conversion of cursor results to list[dict]."""
        # Mock MongoDB client
        mock_mongo_client.return_value = self.mock_client

        # Create a MongoDB node
        node = MongoDBNode(
            name="test_node",
            database="test_db",
            collection="test_coll",
            operation="find",
            query={},
        )

        # Mock cursor result using the specific type check
        from pymongo.cursor import Cursor

        mock_cursor = Mock(spec=Cursor)
        mock_cursor.__iter__ = Mock(
            return_value=iter(
                [{"_id": "1", "name": "doc1"}, {"_id": "2", "name": "doc2"}]
            )
        )

        result = node._convert_result_to_dict(mock_cursor)
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0] == {"_id": "1", "name": "doc1"}
        assert result[1] == {"_id": "2", "name": "doc2"}

    @patch("orcheo.nodes.mongodb.MongoClient")
    def test_convert_command_cursor_to_list_dict(self, mock_mongo_client):
        """Test conversion of command cursor results to list[dict]."""
        # Mock MongoDB client
        mock_mongo_client.return_value = self.mock_client

        # Create a MongoDB node
        node = MongoDBNode(
            name="test_node",
            database="test_db",
            collection="test_coll",
            operation="aggregate",
            query={},
        )

        # Mock command cursor result
        from pymongo.command_cursor import CommandCursor

        mock_cursor = Mock(spec=CommandCursor)
        mock_cursor.__iter__ = Mock(
            return_value=iter([{"_id": "1", "count": 5}, {"_id": "2", "count": 3}])
        )

        result = node._convert_result_to_dict(mock_cursor)
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0] == {"_id": "1", "count": 5}
        assert result[1] == {"_id": "2", "count": 3}

    @patch("orcheo.nodes.mongodb.MongoClient")
    def test_convert_insert_result_to_dict(self, mock_mongo_client):
        """Test conversion of insert result to dict."""
        # Mock MongoDB client
        mock_mongo_client.return_value = self.mock_client

        node = MongoDBNode(
            name="test_node",
            database="test_db",
            collection="test_coll",
            operation="insert_one",
            query={},
        )

        # Mock insert result
        mock_result = Mock(spec=InsertOneResult)
        mock_result.inserted_id = "507f1f77bcf86cd799439011"
        mock_result.acknowledged = True

        result = node._convert_result_to_dict(mock_result)
        assert isinstance(result, dict)
        assert result["operation"] == "insert_one"
        assert result["inserted_id"] == "507f1f77bcf86cd799439011"
        assert result["acknowledged"] is True

    @patch("orcheo.nodes.mongodb.MongoClient")
    def test_convert_insert_many_result_to_dict(self, mock_mongo_client):
        """Test conversion of insert many result to dict."""
        # Mock MongoDB client
        mock_mongo_client.return_value = self.mock_client

        node = MongoDBNode(
            name="test_node",
            database="test_db",
            collection="test_coll",
            operation="insert_many",
            query={},
        )

        # Mock insert many result
        mock_result = Mock(spec=InsertManyResult)
        mock_result.inserted_ids = [
            "507f1f77bcf86cd799439011",
            "507f1f77bcf86cd799439012",
        ]
        mock_result.acknowledged = True

        result = node._convert_result_to_dict(mock_result)
        assert isinstance(result, dict)
        assert result["operation"] == "insert_many"
        assert result["inserted_ids"] == [
            "507f1f77bcf86cd799439011",
            "507f1f77bcf86cd799439012",
        ]
        assert result["acknowledged"] is True

    @patch("orcheo.nodes.mongodb.MongoClient")
    def test_convert_update_result_to_dict(self, mock_mongo_client):
        """Test conversion of update result to dict."""
        # Mock MongoDB client
        mock_mongo_client.return_value = self.mock_client

        node = MongoDBNode(
            name="test_node",
            database="test_db",
            collection="test_coll",
            operation="update_one",
            query={},
        )

        # Mock update result
        mock_result = Mock(spec=UpdateResult)
        mock_result.matched_count = 1
        mock_result.modified_count = 1
        mock_result.upserted_id = None
        mock_result.acknowledged = True

        result = node._convert_result_to_dict(mock_result)
        assert isinstance(result, dict)
        assert result["operation"] == "update"
        assert result["matched_count"] == 1
        assert result["modified_count"] == 1
        assert result["upserted_id"] is None
        assert result["acknowledged"] is True

    @patch("orcheo.nodes.mongodb.MongoClient")
    def test_convert_delete_result_to_dict(self, mock_mongo_client):
        """Test conversion of delete result to dict."""
        # Mock MongoDB client
        mock_mongo_client.return_value = self.mock_client

        node = MongoDBNode(
            name="test_node",
            database="test_db",
            collection="test_coll",
            operation="delete_one",
            query={},
        )

        # Mock delete result
        mock_result = Mock(spec=DeleteResult)
        mock_result.deleted_count = 1
        mock_result.acknowledged = True

        result = node._convert_result_to_dict(mock_result)
        assert isinstance(result, dict)
        assert result["operation"] == "delete"
        assert result["deleted_count"] == 1
        assert result["acknowledged"] is True

    @patch("orcheo.nodes.mongodb.MongoClient")
    def test_convert_bulk_write_result_to_dict(self, mock_mongo_client):
        """Test conversion of bulk write result to dict."""
        # Mock MongoDB client
        mock_mongo_client.return_value = self.mock_client

        node = MongoDBNode(
            name="test_node",
            database="test_db",
            collection="test_coll",
            operation="bulk_write",
            query={},
        )

        # Mock bulk write result
        mock_result = Mock(spec=BulkWriteResult)
        mock_result.inserted_count = 2
        mock_result.matched_count = 3
        mock_result.modified_count = 3
        mock_result.deleted_count = 1
        mock_result.upserted_count = 1
        mock_result.upserted_ids = {0: "507f1f77bcf86cd799439011"}
        mock_result.acknowledged = True

        result = node._convert_result_to_dict(mock_result)
        assert isinstance(result, dict)
        assert result["operation"] == "bulk_write"
        assert result["inserted_count"] == 2
        assert result["matched_count"] == 3
        assert result["modified_count"] == 3
        assert result["deleted_count"] == 1
        assert result["upserted_count"] == 1
        assert result["upserted_ids"] == {"0": "507f1f77bcf86cd799439011"}
        assert result["acknowledged"] is True

    @patch("orcheo.nodes.mongodb.MongoClient")
    def test_convert_bulk_write_result_no_upserted_ids(self, mock_mongo_client):
        """Test conversion of bulk write result with no upserted_ids."""
        # Mock MongoDB client
        mock_mongo_client.return_value = self.mock_client

        node = MongoDBNode(
            name="test_node",
            database="test_db",
            collection="test_coll",
            operation="bulk_write",
            query={},
        )

        # Mock bulk write result with None upserted_ids
        mock_result = Mock(spec=BulkWriteResult)
        mock_result.inserted_count = 2
        mock_result.matched_count = 3
        mock_result.modified_count = 3
        mock_result.deleted_count = 1
        mock_result.upserted_count = 0
        mock_result.upserted_ids = None
        mock_result.acknowledged = True

        result = node._convert_result_to_dict(mock_result)
        assert isinstance(result, dict)
        assert result["upserted_ids"] == {}

    @patch("orcheo.nodes.mongodb.MongoClient")
    def test_convert_primitive_to_dict(self, mock_mongo_client):
        """Test conversion of primitive values to dict."""
        # Mock MongoDB client
        mock_mongo_client.return_value = self.mock_client

        node = MongoDBNode(
            name="test_node",
            database="test_db",
            collection="test_coll",
            operation="count_documents",
            query={},
        )

        # Test integer
        result = node._convert_result_to_dict(42)
        assert result == {"result": 42}

        # Test string
        result = node._convert_result_to_dict("test_string")
        assert result == {"result": "test_string"}

        # Test boolean
        result = node._convert_result_to_dict(True)
        assert result == {"result": True}

        # Test float
        result = node._convert_result_to_dict(3.14)
        assert result == {"result": 3.14}

    @patch("orcheo.nodes.mongodb.MongoClient")
    def test_convert_none_to_dict(self, mock_mongo_client):
        """Test conversion of None result to dict."""
        # Mock MongoDB client
        mock_mongo_client.return_value = self.mock_client

        node = MongoDBNode(
            name="test_node",
            database="test_db",
            collection="test_coll",
            operation="find_one",
            query={},
        )

        result = node._convert_result_to_dict(None)
        assert result == {"result": None}

    @patch("orcheo.nodes.mongodb.MongoClient")
    def test_convert_list_to_list_dict(self, mock_mongo_client):
        """Test conversion of list results to list[dict]."""
        # Mock MongoDB client
        mock_mongo_client.return_value = self.mock_client

        node = MongoDBNode(
            name="test_node",
            database="test_db",
            collection="test_coll",
            operation="distinct",
            query={},
        )

        # Test list of strings
        result = node._convert_result_to_dict(["value1", "value2", "value3"])
        assert isinstance(result, list)
        assert len(result) == 3
        assert result[0] == {"value": "value1"}
        assert result[1] == {"value": "value2"}
        assert result[2] == {"value": "value3"}

        # Test list of dicts
        result = node._convert_result_to_dict([{"key1": "val1"}, {"key2": "val2"}])
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0] == {"key1": "val1"}
        assert result[1] == {"key2": "val2"}

    @patch("orcheo.nodes.mongodb.MongoClient")
    def test_convert_object_with_dict_to_dict(self, mock_mongo_client):
        """Test conversion of objects with __dict__ to dict."""
        # Mock MongoDB client
        mock_mongo_client.return_value = self.mock_client

        node = MongoDBNode(
            name="test_node",
            database="test_db",
            collection="test_coll",
            operation="find",
            query={},
        )

        # Create an object with __dict__
        class CustomObject:
            def __init__(self):
                self.attr1 = "value1"
                self.attr2 = 42

        custom_obj = CustomObject()
        result = node._convert_result_to_dict(custom_obj)
        assert isinstance(result, dict)
        assert result["attr1"] == "value1"
        assert result["attr2"] == 42

    @patch("orcheo.nodes.mongodb.MongoClient")
    def test_convert_unknown_object_to_dict(self, mock_mongo_client):
        """Test conversion of unknown objects to dict using string representation."""
        # Mock MongoDB client
        mock_mongo_client.return_value = self.mock_client

        node = MongoDBNode(
            name="test_node",
            database="test_db",
            collection="test_coll",
            operation="find",
            query={},
        )

        # Test with a complex object without __dict__
        class ComplexObject:
            __slots__ = ()

            def __str__(self):
                return "complex_object_representation"

        complex_obj = ComplexObject()
        result = node._convert_result_to_dict(complex_obj)
        assert isinstance(result, dict)
        assert result["result"] == "complex_object_representation"

    @patch("orcheo.nodes.mongodb.MongoClient")
    def test_run_method(self, mock_mongo_client):
        """Test the run method of MongoDB node."""
        # Mock MongoDB client
        mock_mongo_client.return_value = self.mock_client

        # Mock the collection operation
        self.mock_collection.find.return_value = [{"_id": "1", "name": "doc1"}]

        node = MongoDBNode(
            name="test_node",
            database="test_db",
            collection="test_coll",
            operation="find",
            query={"status": "active"},
        )

        # Create a mock state and config
        state = State(messages=[], outputs={})
        config = {}

        # Run the node
        result = asyncio.run(node.run(state, config))

        # Verify the result
        assert isinstance(result, dict)
        assert "data" in result
        assert isinstance(result["data"], list)
        assert len(result["data"]) == 1
        assert result["data"][0] == {"_id": "1", "name": "doc1"}

        # Verify the operation was called with the correct query
        self.mock_collection.find.assert_called_once_with({"status": "active"})

    @patch("orcheo.nodes.mongodb.MongoClient")
    def test_del_method(self, mock_mongo_client):
        """Test the __del__ method closes the client."""
        # Mock MongoDB client
        mock_mongo_client.return_value = self.mock_client

        node = MongoDBNode(
            name="test_node",
            database="test_db",
            collection="test_coll",
            operation="find",
            query={},
        )

        # Manually call __del__ to test cleanup
        node.__del__()

        # Verify the client close method was called
        self.mock_client.close.assert_called_once()
