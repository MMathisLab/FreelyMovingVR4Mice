

experiments_040424(){

    # python run_lstm.py \
    #     --num_epochs 100 --hidden_units 2

    # python run_lstm.py \
    #     --num_epochs 500 --hidden_units 2

    python run_lstm.py \
        --num_epochs 10 --hidden_units 16 --features all --learning_rate 0.1

    # python run_lstm.py \
    #     --num_epochs 100 --hidden_units 16 --features all_norm

    # python run_lstm.py \
    #     --num_epochs 100 --hidden_units 16 --features pos

    # python run_lstm.py \
    #     --num_epochs 100 --hidden_units 16 --features pos_norm


    # python run_lstm.py \
    #     --num_epochs 100 --hidden_units 16 --features pos_no_aperture
}

experiments_040424\
| parallel --jobs 4 \
'CUDA_VISIBLE_DEVICES=$PARALLEL_JOBSLOT bash -c {}'