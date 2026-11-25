#!/usr/bin/env bash
#
# run_retrieval_app_test.sh
# Runs every test question through the RAG app:
#   uv run python -m retrieval_app "<question>"
#
# Usage:
#   chmod +x run_retrieval_app_test.sh
#   ./run_retrieval_app_test.sh                 # run all questions
#   ./run_retrieval_app_test.sh in              # only in-document questions (Set A)
#   ./run_retrieval_app_test.sh out             # only out-of-document questions (Set B)
#   ./run_retrieval_app_test.sh all results.txt # run all and also save output to a file

set -u

MODE="${1:-all}"
LOGFILE="${2:-}"

# ---------------------------------------------------------------------------
# Set A: questions that SHOULD be answered from HealthWellnessGuide.txt
# ---------------------------------------------------------------------------
IN_DOC_QUESTIONS=(
  "How many minutes of aerobic activity per week?"
  "What should my morning and evening routine look like?"
  "Which exercises does the guide recommend for lower back pain, and how many reps for the Bird Dog?"
  "What bedroom temperature is ideal for sleep?"
  "What is the difference between acute and chronic insomnia?"
  "What are the three parts of the habit loop, and how long does a habit take to form on average?"
  "What is the grounding technique for immediate stress relief?"
  "Which foods are listed as prebiotic, and how much fiber should I eat daily?"
  "What is the 20-20-20 rule, and where does the guide recommend creating tech-free zones?"
  # Bonus: file is inconsistent (Ch. 8 says 1-2 hours, Sleep Checklist says 1 hour)
  "How long before bed should I stop using screens?"
)

# ---------------------------------------------------------------------------
# Set B: questions that should NOT be answerable from the file
# ---------------------------------------------------------------------------
OUT_OF_DOC_QUESTIONS=(
  "What dose of ibuprofen for a migraine?"
  "What are the symptoms and treatments for type 2 diabetes?"
  "Design a 12-week marathon training plan for me."
  "What is the recommended dosage of ibuprofen for a tension headache?"
  "How many calories should a 35-year-old woman eat to lose 1 kg per week?"
  "Who won the 2022 FIFA World Cup?"
  "How do I reverse a linked list in Python?"
  "What is the capital of Australia and its population?"
  "Summarize the main causes of the French Revolution."
)

# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
TOTAL=0
FAILED=0

TEMP_VALUE=0.2

run_set() {
  local label="$1"
  shift
  local questions=("$@")
  local i=1

  echo
  echo "################################################################"
  echo "# ${label}"
  echo "################################################################"

  for q in "${questions[@]}"; do
    TOTAL=$((TOTAL + 1))
    echo
    echo "----------------------------------------------------------------"
    echo "[${label}] Q${i}: ${q}"
    echo "----------------------------------------------------------------"

    uv run python -m retrieval_app "$q"
    status=$?

    if [ "$status" -ne 0 ]; then
      FAILED=$((FAILED + 1))
      echo ">>> Command exited with status ${status}" >&2
    fi
    i=$((i + 1))
  done
}

main() {
  case "$MODE" in
    in)
      run_set "TEMPERATURE VALUE = ${TEMP_VALUE}: SET A - IN DOCUMENT TOPIC" "${IN_DOC_QUESTIONS[@]}"
      ;;
    out)
      run_set "TEMPERATURE VALUE = ${TEMP_VALUE}: SET B - OUT OF DOCUMENT TOPIC" "${OUT_OF_DOC_QUESTIONS[@]}"
      ;;
    all)
      run_set "TEMPERATURE VALUE = ${TEMP_VALUE}: SET A - IN DOCUMENT TOPIC" "${IN_DOC_QUESTIONS[@]}"
      run_set "TEMPERATURE VALUE = ${TEMP_VALUE}: SET B - OUT OF DOCUMENT TOPIC" "${OUT_OF_DOC_QUESTIONS[@]}"
      ;;
    *)
      echo "Unknown mode: ${MODE} (use: all | in | out)" >&2
      exit 2
      ;;
  esac

  echo
  echo "================================================================"
  echo "Done. Ran ${TOTAL} questions, ${FAILED} command failure(s)."
  echo "================================================================"
}

if [ -n "$LOGFILE" ]; then
  main 2>&1 | tee "$LOGFILE"
else
  main
fi