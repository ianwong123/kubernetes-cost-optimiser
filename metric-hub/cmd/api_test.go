package main

import (
	"bytes"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestCostEngineSuccess(t *testing.T) {
	// Create json byte
	var jsonStr = []byte(`{
  "source": "cost-engine",
  "timestamp": "2024-01-01T12:00:00Z",
  "namespace": "default",
  "cluster_info": {
    "vm_count": 3,
    "current_hourly_cost": 1.25
  },
  "deployments": [
    {
      "name": "adservice",
      "current_requests": {
        "cpu_cores": 1.0,
        "memory_mb": 4096
      },
      "current_usage": {
        "cpu_cores": 0.4,
        "memory_mb": 512
      }
    },
    {
      "name": "cartservice",
      "current_requests": {
        "cpu_cores": 1.5,
        "memory_mb": 2048
      },
      "current_usage": {
        "cpu_cores": 0.8,
        "memory_mb": 1024
      }
    }
  ]
}`)
	// instantiate server
	server := NewAPIServer()

	// simulate post request
	req, err := http.NewRequest(http.MethodPost, "/api/v1/metrics/cost", bytes.NewBuffer(jsonStr))
	if err != nil {
		t.Fatal(err)
	}

	// set header so handler knows to expect json
	req.Header.Set("Content-Type", "application/json")

	// simulate response writer
	rr := httptest.NewRecorder()

	// call handler
	server.handleCostEngine(rr, req)

	if status := rr.Code; status != http.StatusCreated {
		t.Errorf("Handler returned wrong status code: got %v, want %v", status, http.StatusCreated)
		return
	}

	expected := "Cost payload accepted"
	if rr.Body.String() != expected {
		t.Errorf("Handler returned unexpected body: got %q, want %q", rr.Body.String(), expected)
	}

	// temporary sleep to print goroutine logs
	time.Sleep(1 * time.Second)
}

func TestForecastSuccess(t *testing.T) {
	var jsonStr = []byte(`{
  "source": "forecast",
  "timestamp": "2024-01-01T12:00:00Z",
  "namespace": "default",
  "deployments": [
    {
      "name": "adservice",
      "predict_peak_24h": {
        "cpu_cores": 0.55,
        "memory_mb": 600
      }
    },
    {
      "name": "cartservice",
      "predict_peak_24h": {
        "cpu_cores": 1.2,
        "memory_mb": 1200
      }
    }
  ]
}
`)

	// instantiate server
	server := NewAPIServer()

	// simulate request
	req, err := http.NewRequest(http.MethodPost, "/metrics/forecast", bytes.NewBuffer(jsonStr))
	if err != nil {
		t.Fatal(err)
	}

	req.Header.Set("Content-Type", "application/json")

	rr := httptest.NewRecorder()

	server.handleForecast(rr, req)

	if status := rr.Code; status != http.StatusCreated {
		t.Errorf("Handler returned wrong status code: got %v, want %v", status, http.StatusCreated)
		return
	}

	expected := "Forecast payload accepted"
	if rr.Body.String() != expected {
		t.Errorf("Handler returned unexpected body: got %q, want %q", rr.Body.String(), expected)
	}
}
