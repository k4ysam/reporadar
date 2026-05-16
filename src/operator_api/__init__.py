"""Operator API service.

CLI + Flask dashboard. The dashboard reads from a denormalized read model
(`src.operator_api.web.queries`) — it does not query each service's tables
directly when joins span multiple services.
"""
