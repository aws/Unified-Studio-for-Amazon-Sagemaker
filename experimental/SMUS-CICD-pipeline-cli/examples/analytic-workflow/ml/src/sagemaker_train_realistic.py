#!/usr/bin/env python3

import argparse
import os
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, classification_report, roc_curve, auc as sklearn_auc, roc_auc_score
from sklearn.preprocessing import label_binarize, StandardScaler
from sklearn.datasets import make_classification
import joblib

def setup_mlflow():
    """Setup MLflow tracking if available"""
    try:
        import mlflow
        import mlflow.sklearn
        import sagemaker_mlflow
        print(f"✅ MLflow version: {mlflow.__version__}")
        
        tracking_server_arn = os.environ.get('MLFLOW_TRACKING_SERVER_ARN')
        experiment_name = "realistic-model-comparison-experiment"
        
        if tracking_server_arn:
            mlflow.set_tracking_uri(tracking_server_arn)
            print(f"MLflow tracking ARN: {tracking_server_arn}")
            
            try:
                mlflow.set_experiment(experiment_name)
                print(f"✅ MLflow experiment set: {experiment_name}")
                return True, None
            except Exception as e:
                print(f"⚠️ MLflow setup failed: {e}")
                return False, None
        else:
            print("No MLflow tracking server ARN found in environment")
            return False, None
            
    except ImportError as e:
        print(f"MLflow not available: {e}")
        return False, None

def create_realistic_dataset():
    """Create a more challenging, realistic dataset"""
    print("Creating realistic classification dataset...")
    
    # Create a more complex dataset with noise
    X, y = make_classification(
        n_samples=2000,           # Larger dataset
        n_features=20,            # More features
        n_informative=12,         # Some features are informative
        n_redundant=4,            # Some redundant features
        n_clusters_per_class=2,   # Multiple clusters per class
        n_classes=3,              # 3 classes
        class_sep=0.8,            # Moderate class separation (not perfect)
        flip_y=0.05,              # 5% label noise
        random_state=42
    )
    
    # Add some additional noise to features
    noise = np.random.normal(0, 0.1, X.shape)
    X = X + noise
    
    # Create feature names
    feature_names = [f'feature_{i:02d}' for i in range(X.shape[1])]
    
    print(f"Dataset created: {X.shape[0]} samples, {X.shape[1]} features, {len(np.unique(y))} classes")
    print(f"Class distribution: {np.bincount(y)}")
    
    return X, y, feature_names

def main():
    parser = argparse.ArgumentParser()
    
    # SageMaker arguments
    parser.add_argument('--model-dir', type=str, default=os.environ.get('SM_MODEL_DIR'))
    parser.add_argument('--train', type=str, default=os.environ.get('SM_CHANNEL_TRAIN'))
    
    # Model hyperparameters
    parser.add_argument('--n-estimators', type=int, default=100)
    parser.add_argument('--max-depth', type=int, default=6)  # Reduced to prevent overfitting
    parser.add_argument('--random-state', type=int, default=42)
    
    args = parser.parse_args()
    
    print("Starting realistic model comparison with MLflow integration...")
    print(f"Model directory: {args.model_dir}")
    
    # Setup MLflow
    use_mlflow, _ = setup_mlflow()
    
    if use_mlflow:
        import mlflow
        import mlflow.sklearn
        
        with mlflow.start_run() as run:
            print(f"✅ MLflow Run ID: {run.info.run_id}")
            
            # Log parameters
            mlflow.log_param("n_estimators", args.n_estimators)
            mlflow.log_param("max_depth", args.max_depth)
            mlflow.log_param("random_state", args.random_state)
            mlflow.log_param("dataset_type", "synthetic_realistic")
            
            # Create realistic dataset
            X, y, feature_names = create_realistic_dataset()
            
            mlflow.log_param("dataset_rows", X.shape[0])
            mlflow.log_param("dataset_cols", X.shape[1])
            mlflow.log_param("n_classes", len(np.unique(y)))
            
            # Split data with stratification
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=args.random_state, stratify=y
            )
            
            # Scale features for SVM and Logistic Regression
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            print(f"Training set: {X_train.shape[0]} samples")
            print(f"Test set: {X_test.shape[0]} samples")
            mlflow.log_param("train_size", X_train.shape[0])
            mlflow.log_param("test_size", X_test.shape[0])
            
            # Define multiple models for comparison
            models = {
                'RandomForest': RandomForestClassifier(
                    n_estimators=args.n_estimators,
                    max_depth=args.max_depth,
                    min_samples_split=10,  # Prevent overfitting
                    min_samples_leaf=5,
                    random_state=args.random_state
                ),
                'GradientBoosting': GradientBoostingClassifier(
                    n_estimators=args.n_estimators,
                    max_depth=args.max_depth,
                    learning_rate=0.1,
                    min_samples_split=10,
                    random_state=args.random_state
                ),
                'LogisticRegression': LogisticRegression(
                    max_iter=1000,
                    random_state=args.random_state,
                    multi_class='ovr'
                ),
                'SVM': SVC(
                    probability=True,  # Enable probability estimates for ROC
                    random_state=args.random_state,
                    gamma='scale'
                )
            }
            
            results = {}
            
            # Train and evaluate each model
            for model_name, model in models.items():
                print(f"\n🔬 Training {model_name}...")
                mlflow.log_param(f"{model_name}_algorithm", model.__class__.__name__)
                
                # Use scaled data for SVM and LogisticRegression
                if model_name in ['SVM', 'LogisticRegression']:
                    X_train_use = X_train_scaled
                    X_test_use = X_test_scaled
                else:
                    X_train_use = X_train
                    X_test_use = X_test
                
                # Cross-validation for more robust evaluation
                cv_scores = cross_val_score(model, X_train_use, y_train, cv=5, scoring='accuracy')
                cv_mean = cv_scores.mean()
                cv_std = cv_scores.std()
                
                print(f"Cross-validation: {cv_mean:.4f} (+/- {cv_std * 2:.4f})")
                mlflow.log_metric(f"{model_name}_cv_accuracy_mean", cv_mean)
                mlflow.log_metric(f"{model_name}_cv_accuracy_std", cv_std)
                
                # Train on full training set
                model.fit(X_train_use, y_train)
                
                # Predictions
                y_pred = model.predict(X_test_use)
                y_pred_proba = model.predict_proba(X_test_use)
                
                # Calculate metrics
                accuracy = accuracy_score(y_test, y_pred)
                
                # Multi-class ROC AUC
                y_test_bin = label_binarize(y_test, classes=[0, 1, 2])
                n_classes = y_test_bin.shape[1]
                
                # Compute ROC curve and AUC for each class
                fpr = dict()
                tpr = dict()
                roc_auc = dict()
                
                for i in range(n_classes):
                    fpr[i], tpr[i], _ = roc_curve(y_test_bin[:, i], y_pred_proba[:, i])
                    roc_auc[i] = sklearn_auc(fpr[i], tpr[i])
                
                # Compute micro-average ROC curve
                fpr["micro"], tpr["micro"], _ = roc_curve(y_test_bin.ravel(), y_pred_proba.ravel())
                roc_auc["micro"] = sklearn_auc(fpr["micro"], tpr["micro"])
                
                # Macro-average ROC AUC
                macro_roc_auc = roc_auc_score(y_test, y_pred_proba, multi_class='ovr', average='macro')
                
                results[model_name] = {
                    'model': model,
                    'accuracy': accuracy,
                    'cv_accuracy': cv_mean,
                    'cv_std': cv_std,
                    'macro_roc_auc': macro_roc_auc,
                    'fpr': fpr,
                    'tpr': tpr,
                    'roc_auc': roc_auc,
                    'y_pred': y_pred,
                    'y_pred_proba': y_pred_proba
                }
                
                # Log metrics to MLflow
                mlflow.log_metric(f"{model_name}_test_accuracy", accuracy)
                mlflow.log_metric(f"{model_name}_macro_roc_auc", macro_roc_auc)
                
                for i in range(n_classes):
                    mlflow.log_metric(f"{model_name}_roc_auc_class_{i}", roc_auc[i])
                
                print(f"✅ {model_name}:")
                print(f"   Test Accuracy: {accuracy:.4f}")
                print(f"   CV Accuracy: {cv_mean:.4f} (+/- {cv_std * 2:.4f})")
                print(f"   Macro ROC AUC: {macro_roc_auc:.4f}")
                
                # Classification report
                report = classification_report(y_test, y_pred)
                print(f"Classification Report:\n{report}")
            
            # Create comprehensive ROC curve comparison plot
            try:
                import matplotlib
                matplotlib.use('Agg')
                import matplotlib.pyplot as plt
                
                fig, axes = plt.subplots(2, 2, figsize=(15, 12))
                
                # Plot 1: Micro-average ROC curves comparison
                ax1 = axes[0, 0]
                colors = ['red', 'blue', 'green', 'orange']
                model_names = list(results.keys())
                
                for idx, model_name in enumerate(model_names):
                    result = results[model_name]
                    ax1.plot(result['fpr']['micro'], result['tpr']['micro'],
                            color=colors[idx], linestyle='-', linewidth=2,
                            label=f'{model_name} (AUC = {result["roc_auc"]["micro"]:.3f})')
                
                ax1.plot([0, 1], [0, 1], 'k--', alpha=0.5, label='Random')
                ax1.set_xlim([0.0, 1.0])
                ax1.set_ylim([0.0, 1.05])
                ax1.set_xlabel('False Positive Rate')
                ax1.set_ylabel('True Positive Rate')
                ax1.set_title('ROC Curves - Micro Average')
                ax1.legend(loc="lower right")
                ax1.grid(True, alpha=0.3)
                
                # Plot 2: Accuracy comparison
                ax2 = axes[0, 1]
                model_names = list(results.keys())
                test_accuracies = [results[name]['accuracy'] for name in model_names]
                cv_accuracies = [results[name]['cv_accuracy'] for name in model_names]
                cv_stds = [results[name]['cv_std'] for name in model_names]
                
                x = np.arange(len(model_names))
                width = 0.35
                
                ax2.bar(x - width/2, test_accuracies, width, label='Test Accuracy', alpha=0.8)
                ax2.errorbar(x + width/2, cv_accuracies, yerr=cv_stds, 
                           fmt='o', label='CV Accuracy', capsize=5)
                
                ax2.set_xlabel('Models')
                ax2.set_ylabel('Accuracy')
                ax2.set_title('Model Performance Comparison')
                ax2.set_xticks(x)
                ax2.set_xticklabels(model_names, rotation=45)
                ax2.legend()
                ax2.grid(True, alpha=0.3)
                
                # Plot 3: ROC AUC comparison
                ax3 = axes[1, 0]
                macro_aucs = [results[name]['macro_roc_auc'] for name in model_names]
                
                bars = ax3.bar(model_names, macro_aucs, alpha=0.8, color=colors[:len(model_names)])
                ax3.set_xlabel('Models')
                ax3.set_ylabel('Macro ROC AUC')
                ax3.set_title('ROC AUC Comparison')
                ax3.set_xticklabels(model_names, rotation=45)
                ax3.grid(True, alpha=0.3)
                
                # Add value labels on bars
                for bar, auc in zip(bars, macro_aucs):
                    height = bar.get_height()
                    ax3.text(bar.get_x() + bar.get_width()/2., height + 0.01,
                            f'{auc:.3f}', ha='center', va='bottom')
                
                # Plot 4: Per-class ROC for best model
                best_model_name = max(results.keys(), key=lambda k: results[k]['macro_roc_auc'])
                best_result = results[best_model_name]
                
                ax4 = axes[1, 1]
                class_colors = ['red', 'green', 'blue']
                
                for i in range(n_classes):
                    ax4.plot(best_result['fpr'][i], best_result['tpr'][i], 
                            color=class_colors[i], linewidth=2,
                            label=f'Class {i} (AUC = {best_result["roc_auc"][i]:.3f})')
                
                ax4.plot([0, 1], [0, 1], 'k--', alpha=0.5)
                ax4.set_xlim([0.0, 1.0])
                ax4.set_ylim([0.0, 1.05])
                ax4.set_xlabel('False Positive Rate')
                ax4.set_ylabel('True Positive Rate')
                ax4.set_title(f'{best_model_name} - Per Class ROC')
                ax4.legend(loc="lower right")
                ax4.grid(True, alpha=0.3)
                
                plt.tight_layout()
                plt.savefig('/opt/ml/model/realistic_model_comparison.png', dpi=150, bbox_inches='tight')
                mlflow.log_artifact('/opt/ml/model/realistic_model_comparison.png')
                plt.close()
                print("✅ Comprehensive comparison plot saved and logged to MLflow")
                
            except Exception as e:
                print(f"⚠️ Could not create plots: {e}")
            
            # Determine best model based on cross-validation
            best_model_name = max(results.keys(), key=lambda k: results[k]['cv_accuracy'])
            best_model = results[best_model_name]['model']
            best_accuracy = results[best_model_name]['accuracy']
            best_cv_accuracy = results[best_model_name]['cv_accuracy']
            best_roc_auc = results[best_model_name]['macro_roc_auc']
            
            print(f"\n🏆 Best Model (by CV): {best_model_name}")
            print(f"   Test Accuracy: {best_accuracy:.4f}")
            print(f"   CV Accuracy: {best_cv_accuracy:.4f}")
            print(f"   Macro ROC AUC: {best_roc_auc:.4f}")
            
            # Log best model info
            mlflow.log_param("best_model", best_model_name)
            mlflow.log_metric("best_test_accuracy", best_accuracy)
            mlflow.log_metric("best_cv_accuracy", best_cv_accuracy)
            mlflow.log_metric("best_macro_roc_auc", best_roc_auc)
            
            # Log model to MLflow
            try:
                mlflow.sklearn.log_model(
                    best_model, 
                    "model",
                    registered_model_name="realistic-classifier-v1"
                )
                print("✅ Model logged to MLflow with auto-registration")
            except Exception as e:
                print(f"Warning: Could not register model: {e}")
                mlflow.sklearn.log_model(best_model, "model")
                print("✅ Model logged to MLflow without registration")
            
            # Save model for SageMaker
            joblib.dump(best_model, os.path.join(args.model_dir, "model.joblib"))
            
            # Save feature names and scaler
            with open(os.path.join(args.model_dir, "feature_names.txt"), 'w') as f:
                for name in feature_names:
                    f.write(f"{name}\n")
            
            if best_model_name in ['SVM', 'LogisticRegression']:
                joblib.dump(scaler, os.path.join(args.model_dir, "scaler.joblib"))
            
            # Save model metadata
            metadata = {
                "best_model": best_model_name,
                "test_accuracy": best_accuracy,
                "cv_accuracy": best_cv_accuracy,
                "macro_roc_auc": best_roc_auc,
                "n_estimators": args.n_estimators,
                "max_depth": args.max_depth,
                "feature_count": len(feature_names),
                "training_samples": len(X_train),
                "test_samples": len(X_test),
                "mlflow_run_id": run.info.run_id,
                "all_results": {name: {
                    "test_accuracy": results[name]["accuracy"],
                    "cv_accuracy": results[name]["cv_accuracy"],
                    "macro_roc_auc": results[name]["macro_roc_auc"]
                } for name in results.keys()}
            }
            
            import json
            with open(os.path.join(args.model_dir, "metadata.json"), 'w') as f:
                json.dump(metadata, f, indent=2)
            
            print("✅ Realistic model comparison completed successfully!")
            print(f"Model saved to: {args.model_dir}")
            print(f"MLflow Run ID: {run.info.run_id}")
    
    else:
        print("Running without MLflow - basic training...")
        # Fallback without MLflow
        X, y, feature_names = create_realistic_dataset()
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        model = RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42)
        model.fit(X_train, y_train)
        
        accuracy = accuracy_score(y_test, model.predict(X_test))
        print(f"Test Accuracy: {accuracy:.4f}")
        
        joblib.dump(model, os.path.join(args.model_dir, "model.joblib"))

if __name__ == "__main__":
    main()
