package main

import (
	"context"
	"log/slog"
	"os"

	"github.com/google/uuid"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

type ctxKey string

const (
	traceIDKey ctxKey = "trace_id"
	spanIDKey  ctxKey = "span_id"
)

var logLinesDropped = promauto.NewCounter(
	prometheus.CounterOpts{
		Name: "log_lines_dropped_total",
		Help: "Total number of log lines dropped due to a full async buffer.",
	},
)

var appLogger *slog.Logger

type asyncWriter struct {
	ch chan []byte
}

func newAsyncWriter(bufSize int) *asyncWriter {
	w := &asyncWriter{ch: make(chan []byte, bufSize)}
	go func() {
		for b := range w.ch {
			os.Stdout.Write(b)
		}
	}()
	return w
}

func (w *asyncWriter) Write(p []byte) (int, error) {
	b := make([]byte, len(p))
	copy(b, p)
	select {
	case w.ch <- b:
	default:
		logLinesDropped.Inc()
	}
	return len(p), nil
}

type serviceHandler struct {
	inner   slog.Handler
	service string
}

func (h *serviceHandler) Enabled(ctx context.Context, level slog.Level) bool {
	return h.inner.Enabled(ctx, level)
}

func (h *serviceHandler) Handle(ctx context.Context, r slog.Record) error {
	r.AddAttrs(slog.String("service", h.service))
	if v, ok := ctx.Value(traceIDKey).(string); ok && v != "" {
		r.AddAttrs(slog.String("trace_id", v))
	}
	if v, ok := ctx.Value(spanIDKey).(string); ok && v != "" {
		r.AddAttrs(slog.String("span_id", v))
	}
	return h.inner.Handle(ctx, r)
}

func (h *serviceHandler) WithAttrs(attrs []slog.Attr) slog.Handler {
	return &serviceHandler{inner: h.inner.WithAttrs(attrs), service: h.service}
}

func (h *serviceHandler) WithGroup(name string) slog.Handler {
	return &serviceHandler{inner: h.inner.WithGroup(name), service: h.service}
}

func initLogger() {
	w := newAsyncWriter(4096)
	jsonHandler := slog.NewJSONHandler(w, &slog.HandlerOptions{
		Level: slog.LevelDebug,
		ReplaceAttr: func(_ []string, a slog.Attr) slog.Attr {
			if a.Key == slog.TimeKey {
				a.Key = "timestamp"
			}
			return a
		},
	})
	appLogger = slog.New(&serviceHandler{inner: jsonHandler, service: "api-service"})
	slog.SetDefault(appLogger)
}

func newTraceContext(parent context.Context) context.Context {
	ctx := context.WithValue(parent, traceIDKey, uuid.New().String())
	return context.WithValue(ctx, spanIDKey, uuid.New().String()[:16])
}

func withChildSpan(ctx context.Context) context.Context {
	return context.WithValue(ctx, spanIDKey, uuid.New().String()[:16])
}
