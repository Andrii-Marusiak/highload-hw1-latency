package main

import (
	"net/http"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

var (
	httpRequestsTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "http_requests_total",
			Help: "Total number of HTTP requests partitioned by method, endpoint, and status code.",
		},
		[]string{"method", "endpoint", "status_code"},
	)

	httpRequestDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "http_request_duration_seconds",
			Help:    "HTTP request latency in seconds partitioned by method and endpoint.",
			Buckets: []float64{0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 1, 2.5, 5, 10},
		},
		[]string{"method", "endpoint"},
	)

	connectionPoolActive = promauto.NewGauge(
		prometheus.GaugeOpts{
			Name: "connection_pool_active",
			Help: "Number of active connections currently in use.",
		},
	)

	connectionPoolMax = promauto.NewGauge(
		prometheus.GaugeOpts{
			Name: "connection_pool_max",
			Help: "Maximum number of connections allowed in the pool.",
		},
	)

	connectionPoolWaiting = promauto.NewGauge(
		prometheus.GaugeOpts{
			Name: "connection_pool_waiting",
			Help: "Number of requests waiting for a connection from the pool.",
		},
	)
)

func startMetricsServer() {
	mux := http.NewServeMux()
	mux.Handle("/metrics", promhttp.Handler())
	go func() {
		if err := http.ListenAndServe(":9090", mux); err != nil && err != http.ErrServerClosed {
			panic(err)
		}
	}()
}
