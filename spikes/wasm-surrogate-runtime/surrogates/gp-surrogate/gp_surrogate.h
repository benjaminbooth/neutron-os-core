/**
 * Gaussian Process Surrogate Model
 * 
 * A simple GP implementation for demonstration purposes.
 * In production, this would be generated from a trained sklearn/GPy model.
 * 
 * This implementation uses a squared exponential (RBF) kernel:
 *   k(x, x') = σ² * exp(-||x - x'||² / (2 * l²))
 * 
 * where σ² is the signal variance and l is the length scale.
 */

#ifndef GP_SURROGATE_H
#define GP_SURROGATE_H

#include <stdint.h>
#include <stdbool.h>

/* Model configuration */
#define GP_INPUT_DIM 5      /* Number of input features */
#define GP_OUTPUT_DIM 1     /* Number of output values */
#define GP_N_TRAIN 100      /* Number of training points */

/* Model metadata */
#define GP_MODEL_ID "gp-mcnp-keff-v1"
#define GP_VERSION "0.1.0"
#define GP_TRAINING_HASH "sha256:abc123..."
#define GP_DESCRIPTION "GP surrogate for MCNP k-effective predictions"

/* Kernel hyperparameters (would be loaded from trained model) */
#define GP_LENGTH_SCALE 1.0
#define GP_SIGNAL_VARIANCE 1.0
#define GP_NOISE_VARIANCE 0.01

/**
 * Model state structure
 * In a real implementation, this would hold the trained parameters:
 * - Training data X (n_train × input_dim)
 * - Alpha coefficients (K^{-1} y)
 * - Kernel hyperparameters
 */
typedef struct {
    double X_train[GP_N_TRAIN][GP_INPUT_DIM];  /* Training inputs */
    double alpha[GP_N_TRAIN];                   /* K^{-1} y */
    double length_scale;
    double signal_variance;
    double noise_variance;
    bool initialized;
} GPModel;

/**
 * Prediction output structure
 */
typedef struct {
    double mean[GP_OUTPUT_DIM];
    double variance[GP_OUTPUT_DIM];
    uint64_t computation_time_us;
} GPPrediction;

/**
 * Validation result
 */
typedef struct {
    bool valid;
    const char* message;
} GPValidation;

/* Public API (exported to WASM) */

/**
 * Initialize the model
 * Returns 0 on success, negative on error
 */
int gp_init(void);

/**
 * Make a prediction
 * 
 * @param input Array of GP_INPUT_DIM features
 * @param output Pointer to GPPrediction to fill
 * @return 0 on success, negative on error
 */
int gp_predict(const double* input, GPPrediction* output);

/**
 * Validate model state
 */
GPValidation gp_validate(void);

/**
 * Get input dimension
 */
uint32_t gp_get_input_dim(void);

/**
 * Get output dimension
 */
uint32_t gp_get_output_dim(void);

/**
 * Get model ID
 */
const char* gp_get_model_id(void);

/**
 * Get model version
 */
const char* gp_get_version(void);

#endif /* GP_SURROGATE_H */
