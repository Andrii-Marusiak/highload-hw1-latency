package main

import (
	"log/slog"
	"net/http"
	"regexp"
	"strconv"
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

		rw := newResponseWriter(w)
		start := time.Now()
		route := sanitizeRoute(r.Pattern)

		slog.InfoContext(ctx, "request started",
			slog.String("method", r.Method),
			slog.String("endpoint", route),
		)

		next.ServeHTTP(rw, r)

		duration := time.Since(start).Seconds()
		status := strconv.Itoa(rw.statusCode)

		httpRequestsTotal.WithLabelValues(r.Method, route, status).Inc()
		httpRequestDuration.WithLabelValues(r.Method, route).Observe(duration)

		slog.InfoContext(ctx, "request completed",
			slog.String("method", r.Method),
			slog.String("endpoint", route),
			slog.String("status_code", status),
			slog.Float64("duration_seconds", duration),
		)
	})
}
