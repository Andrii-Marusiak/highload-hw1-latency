package main

import (
	"fmt"
	"log/slog"
	"net/http"
	"regexp"
	"strings"
	"time"
)

var pathParamRe = regexp.MustCompile(`\{[^}]+\}`)

type responseWriter struct {
	http.ResponseWriter
	statusCode int
}

func newResponseWriter(w http.ResponseWriter) *responseWriter {
	return &responseWriter{ResponseWriter: w, statusCode: http.StatusOK}
}

func (rw *responseWriter) WriteHeader(code int) {
	rw.statusCode = code
	rw.ResponseWriter.WriteHeader(code)
}

func sanitizeRoute(pattern string) string {
	parts := strings.Fields(pattern)
	path := pattern
	if len(parts) == 2 {
		path = parts[1]
	}
	return pathParamRe.ReplaceAllStringFunc(path, func(s string) string {
		return ":" + s[1:len(s)-1]
	})
}

func observabilityMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		ctx := newTraceContext(r.Context())
		r = r.WithContext(ctx)

		GoroutinesActive.Inc()
		defer GoroutinesActive.Dec()

		rw := newResponseWriter(w)
		start := time.Now()

		next.ServeHTTP(rw, r)

		durationMs := float64(time.Since(start).Milliseconds())
		route := sanitizeRoute(r.Pattern)
		statusClass := fmt.Sprintf("%dxx", rw.statusCode/100)

		HTTPRequestsTotal.WithLabelValues(route, r.Method, statusClass).Inc()
		HTTPRequestDuration.WithLabelValues(route, r.Method).Observe(durationMs)

		if rw.statusCode >= 500 {
			HTTPErrorsTotal.WithLabelValues(route, "server_error").Inc()
		}

		slog.InfoContext(ctx, "request completed",
			slog.String("method", r.Method),
			slog.String("route", route),
			slog.Int("status", rw.statusCode),
			slog.String("status_class", statusClass),
			slog.Float64("duration_ms", durationMs),
		)
	})
}
