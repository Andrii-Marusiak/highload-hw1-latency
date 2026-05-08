package main

import (
	"fmt"
	"log/slog"
	"math/rand"
	"net/http"
	"time"
)

func healthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	fmt.Fprint(w, `{"status":"ok"}`)
}

func getUserHandler(w http.ResponseWriter, r *http.Request) {
	connectionPoolActive.Inc()
	connectionPoolWaiting.Add(float64(rand.Intn(5)))

	latency := time.Duration(10+rand.Intn(191)) * time.Millisecond
	time.Sleep(latency)

	connectionPoolActive.Dec()
	connectionPoolWaiting.Set(0)

	userID := r.PathValue("id")
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	fmt.Fprintf(w, `{"id":%q,"name":"User %s"}`, userID, userID)
}

func createOrderHandler(w http.ResponseWriter, r *http.Request) {
	statusCode := http.StatusCreated
	body := `{"id":"order-new","status":"created"}`

	if rand.Float64() < 0.1 {
		statusCode = http.StatusInternalServerError
		body = `{"error":"internal server error"}`
		slog.ErrorContext(r.Context(), "order creation failed",
			slog.String("method", r.Method),
			slog.String("endpoint", "/api/orders"),
		)
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(statusCode)
	fmt.Fprint(w, body)
}

func slowHandler(w http.ResponseWriter, r *http.Request) {
	connectionPoolActive.Inc()
	connectionPoolWaiting.Add(float64(rand.Intn(10)))

	latency := time.Duration(500+rand.Intn(1501)) * time.Millisecond
	time.Sleep(latency)

	connectionPoolActive.Dec()
	connectionPoolWaiting.Set(0)

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	fmt.Fprint(w, `{"status":"done"}`)
}
