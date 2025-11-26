package internal

import "time"

type Resources struct {
	CPUCores float64 `json:"cpu_cores" validate:"required,gt=0"`
	MemoryMB float64 `json:"memory_mb" validate:"required,gt=0"`
}

type CostDeployment struct {
	Name            string    `json:"name" validate:"required"`
	CurrentRequests Resources `json:"current_requests" validate:"required"`
	CurrentUsage    Resources `json:"current_usage" validate:"required"`
}

type ForecastDeployment struct {
	Name           string    `json:"name" validate:"required"`
	PredictPeak24h Resources `json:"predict_peak_24h" validate:"required"`
}

type ClusterTotals struct {
	VmCount float64 `json:"vm_count" validate:"required,gt=0"`
	Cost    float64 `json:"current_hourly_cost" validate:"required,gt=0"`
}

type CostPayload struct {
	Source        string           `json:"source" validate:"required"`
	Timestamp     time.Time        `json:"timestamp" validate:"required"`
	Namespace     string           `json:"namespace" validate:"required,eq=default"`
	ClusterTotals ClusterTotals    `json:"cluster_totals" validate:"required"`
	Deployments   []CostDeployment `json:"deployments" validate:"required,min=1,dive"`
}

type ForecastPayload struct {
	Source      string               `json:"source" validate:"required"`
	Timestamp   time.Time            `json:"timestamp" validate:"required"`
	Namespace   string               `json:"namespace" validate:"required,eq=default"`
	Deployments []ForecastDeployment `json:"deployments" validate:"required,min=1,dive"`
}
