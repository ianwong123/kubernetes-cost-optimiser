package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"os"

	"github.com/ianwong123/kubernetes-cost-optimiser/metric-hub/internal"
)

type APIServer struct {
	Validator  internal.ValidatorInterface
	Aggregator internal.AggregatorInterface
}

// cosntructor
func NewAPIServer() *APIServer {
	redisAddr := os.Getenv("REDIS_SERVICE_ADDR")
	redisPass := os.Getenv("REDIS_SERVICE_PASS")
	return &APIServer{
		Validator:  internal.NewValidator(),
		Aggregator: internal.NewAggregator(redisAddr, redisPass),
	}
}

// start http server
func (s *APIServer) Start() error {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /api/v1/metrics/cost", s.handleCostEngine)
	mux.HandleFunc("POST /api/v1/metrics/forecast", s.handleForecast)

	return http.ListenAndServe(":8008", mux)
}

// handler function for POST /metrics/cost request
func (s *APIServer) handleCostEngine(w http.ResponseWriter, r *http.Request) {
	var payload internal.CostPayload

	dec := json.NewDecoder(r.Body)
	if err := dec.Decode(&payload); err != nil {
		http.Error(w, "Bad request", http.StatusBadRequest)
		return
	}

	if err := s.Validator.Validate(&payload); err != nil {
		http.Error(w, "Invalid JSON format", http.StatusBadRequest)
		return
	}

	if err := s.Aggregator.SaveCostPayload(&payload); err != nil {
		http.Error(w, "Failed to save", http.StatusInternalServerError)
		return
	}

	fmt.Println("Received post request for api/v1/metrics/cost")
	w.WriteHeader(http.StatusCreated)
	w.Write([]byte("Cost payload accepted"))

}

// handler function for POST /metrics/forecast
func (s *APIServer) handleForecast(w http.ResponseWriter, r *http.Request) {
	var payload internal.ForecastPayload
	dec := json.NewDecoder(r.Body)
	if err := dec.Decode(&payload); err != nil {
		http.Error(w, "Bad request", http.StatusBadRequest)
		return
	}

	if err := s.Validator.Validate(&payload); err != nil {
		http.Error(w, "Invalid JSON format", http.StatusBadRequest)
		return
	}

	if err := s.Aggregator.FetchPayload(&payload); err != nil {
		fmt.Printf("Aggregator error %v\n", err)
		http.Error(w, "Failed to process forecast", http.StatusBadRequest)
	}

	fmt.Println("Received post request for api/v1/metrics/forecast")
	w.WriteHeader(http.StatusCreated)
	w.Write([]byte("Forecast payload accepted"))

}
