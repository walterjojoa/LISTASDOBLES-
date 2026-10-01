"""Doubly linked list implemented from scratch to manage stream scenes."""


class Node:
    """A single node holding scene data and links to its neighbours."""

    __slots__ = ("data", "prev", "next")

    def __init__(self, data):
        self.data = data
        self.prev = None
        self.next = None


class DoublyLinkedList:
    """Ordered sequence of scenes with a `current` pointer (the live scene)."""

    def __init__(self):
        self.head = None
        self.tail = None
        self.current = None
        self._size = 0

    def __len__(self):
        return self._size

    def __iter__(self):
        node = self.head
        while node:
            yield node.data
            node = node.next

    def is_empty(self):
        return self._size == 0

    def has_next(self):
        return self.current is not None and self.current.next is not None

    def has_previous(self):
        return self.current is not None and self.current.prev is not None

    def append(self, data):
        """Add a scene at the end of the list. O(1) thanks to the tail pointer."""
        node = Node(data)
        if self.is_empty():
            self.head = self.tail = self.current = node
        else:
            node.prev = self.tail
            self.tail.next = node
            self.tail = node
        self._size += 1
        return node

    def insert_after_current(self, data):
        """Insert a scene right after the live scene. O(1)."""
        if self.is_empty():
            return self.append(data)
        node = Node(data)
        node.prev = self.current
        node.next = self.current.next
        if self.current.next:
            self.current.next.prev = node
        else:
            self.tail = node  # inserted after the old tail
        self.current.next = node
        self._size += 1
        return node

    def move_next(self):
        """Make the next scene live."""
        if not self.has_next():
            raise IndexError("Already on the last scene.")
        self.current = self.current.next
        return self.current.data

    def move_previous(self):
        """Make the previous scene live."""
        if not self.has_previous():
            raise IndexError("Already on the first scene.")
        self.current = self.current.prev
        return self.current.data

    def remove_current(self):
        """Unlink the live scene; the next scene (or previous, at the end) goes live."""
        if self.is_empty():
            raise IndexError("There are no scenes to remove.")
        node = self.current
        if node.prev:
            node.prev.next = node.next
        else:
            self.head = node.next
        if node.next:
            node.next.prev = node.prev
        else:
            self.tail = node.prev
        self.current = node.next or node.prev
        node.prev = node.next = None
        self._size -= 1
        return node.data

    def to_list(self):
        """Return all scene data from head to tail."""
        return list(self)
