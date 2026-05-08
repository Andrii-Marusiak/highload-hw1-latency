package main

import (
	"context"
	"log/slog"
	"net/http"
)

func main() {
	initLogger()
	startMetricsServer()

	slog.InfoContext(context.Background(), "service starting",
		slog.String("app_port", "8080"),
		slog.String("metrics_port", "9090"),
	)

	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/health", healthHandler)
	mux.HandleFunc("GET /api/users/{id}", getUserHandler)
	mux.HandleFunc("POST /api/orders", createOrderHandler)
	mux.HandleFunc("GET /api/slow", slowHandler)

	if err := http.ListenAndServe(":8080", observabilityMiddleware(mux)); err != nil {
		panic(err)
	}
}
