package main

import (
	"net/http"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

var (
	HTTPRequestsTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "http_requests_total",
			Help: "Total HTTP requests by route, method, and status class",
		},
		[]string{"route", "method", "status_class"},
	)

	HTTPRequestDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "http_request_duration_ms",
			Help:    "HTTP request latency in milliseconds",
			Buckets: []float64{5, 10, 25, 50, 75, 100, 150, 200, 300, 500, 1000, 2500, 5000, 10000, 15000},
		},
		[]string{"route", "method"},
	)

	HTTPErrorsTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "http_errors_total",
			Help: "Total HTTP 5xx errors by route",
		},
		[]string{"route", "error_type"},
	)

	GoroutinesActive = promauto.NewGauge(prometheus.GaugeOpts{
		Name: "goroutines_active",
		Help: "Number of goroutines currently processing requests",
	})

	RequestsQueued = promauto.NewGauge(prometheus.GaugeOpts{
		Name: "requests_queued",
		Help: "Number of requests waiting in the accept queue",
	})

	DBConnectionsActive = promauto.NewGauge(prometheus.GaugeOpts{
		Name: "db_connections_active",
		Help: "Number of active database connections",
	})

	DBConnectionsWaiting = promauto.NewGauge(prometheus.GaugeOpts{
		Name: "db_connections_waiting",
		Help: "Number of requests waiting for a DB connection",
	})

	DBQueryErrorsTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "db_query_errors_total",
			Help: "Total failed DB queries by operation type",
		},
		[]string{"operation"},
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
