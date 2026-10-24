# Complétion facultative Bash : source config/ossgeo-completion.bash
_ossgeo_complete() {
    local current previous word command="" choices candidate
    current="${COMP_WORDS[COMP_CWORD]}"
    previous="${COMP_WORDS[COMP_CWORD-1]}"
    COMPREPLY=()
    if [[ "$previous" == "--root" ]]; then
        while IFS= read -r candidate; do COMPREPLY+=("$candidate"); done < <(compgen -d -- "$current")
        return
    fi
    if [[ "$previous" == "--profile" ]]; then
        choices="core all"
    else
        for word in "${COMP_WORDS[@]:1}"; do
            case "$word" in fetch|validate|prepare|status) command="$word"; break ;; esac
        done
        case "$command" in
            fetch) choices="--profile --update --help" ;;
            validate|prepare|status) choices="--help" ;;
            *) choices="fetch validate prepare status --root --help --version" ;;
        esac
    fi
    while IFS= read -r candidate; do COMPREPLY+=("$candidate"); done < <(compgen -W "$choices" -- "$current")
}
complete -F _ossgeo_complete ossgeo open-sauce
